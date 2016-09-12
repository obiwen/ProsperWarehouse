'''connection.py: a framework for defining/managing database connections'''

import abc
import importlib.util
#import configparser

from plumbum import local

import prosper.warehouse.Utilities as table_utils #TODO, required?
#from prosper.common.utilities import get_config
class TableType:
    '''enumeration for tabletypes'''
    MySQL = 'MySQL'
    Postgress = 'Postgress'
    NOTDEFINED = 'NOTDEFINED'

    def set_table_type(self, string_enum):
        '''roll enum from string'''
        if string_enum.lower() == 'mysql':
            return self.MySQL
        elif string_enum.lower() == 'postgress':
            return self.Postgress

        else:
            return self.NOTDEFINED

class Database(metaclass=abc.ABCMeta):
    '''parent class for holding database connection info'''
    def __init__(self, datasource_name):
        '''basic info about all databases'''
        self.datasource_name = datasource_name
        self.table_name = ''
        self.local_path = self.set_local_path()
        print('--DATABASE: made con/cur')

        self.index_key = None
        self.primary_keys, self.data_keys = self.get_keys()
        print('--DATABASE: got keys from config')


        self.table_type = self._define_table_type()
        try:
            self.test_table()
        except Exception as error_msg:
            raise error_msg

    def __str__(self):
        return self.datasource_name

    @abc.abstractmethod
    def set_local_path(self):
        '''set CWD path for sourcing files'''
        pass

    @abc.abstractmethod
    def _define_table_type(self):
        '''helps define technology for class definition'''
        pass

    @abc.abstractmethod
    def get_keys(self):
        '''get primary/data keys for query manipulation'''
        pass

    @abc.abstractmethod
    def _set_info(self):
        '''save useful info about table/datasource'''
        pass

    @abc.abstractmethod
    def get_connection(self):
        '''get con[nection] for database handles'''
        pass

    @abc.abstractmethod
    def get_data(self, *args, **kwargs):
        '''process queries to fetch data'''
        #**kwargs: filter query keys
        #*args: data keys to return
        pass

    @abc.abstractmethod
    def put_data(self, payload):
        '''save data to table (if allowed)'''
        pass

    @abc.abstractmethod
    def test_table(self):
        '''validate that datasource exists, and is ready for data'''
        pass

    @abc.abstractmethod
    def _direct_query(self, query_str):
        '''some tests require direct SQL execution.  Support those calls internally ONLY'''
        pass

class SQLTable(Database):
    '''child class for handling TimeSeries databases'''
    def __init__(self, datasource_name):
        '''Traditional SQL-style hook setup'''
        self._connection,self._cursor = self.get_connection()
        self.table_name, self.schema_name = self._set_info()
        super().__init__(datasource_name)

    def _direct_query(self, query_str):
        '''direct query for SQL tables'''
        #TODO: if/else check for every query seems wasteful, rework?
        if self.table_type == TableType.MySQL:
            #MYSQL EXECUTE
            try:
                self._cursor.execute(query_str)
                query_result = self._cursor.fetchall()
            except Exception as error_msg:
                raise error_msg

            return query_result

        elif self.table_type == TableType.Postgress:
            #POSTGRESS EXECUTE
            pass

        else:
            raise UnsupportedTableType(
                'unsupported table type: ' + str(self.table_type),
                self.table_name
                )

    def _create_table(self, full_create_string):
        '''handles executing table-create query'''


        command_list = full_create_string.split(';')
        for command in command_list:
            if command.startswith('--') or \
               command == '\n':
                #don't execute comments or blank lines
                #FIXME hacky as fuck
                continue

            self._cursor.execute(command)
            self._connection.commit()

    def test_table_exists(
            self,
            table_name,
            schema_name,
            debug = False,
            logger = None
    ):
        '''basic test for table existing'''
        exists_query = ''
        exists_result = False #TODO: remove?
        if self.table_type == TableType.MySQL:
            exists_query = \
            '''SHOW TABLES LIKE \'{table_name}\''''.\
                format(
                    table_name=table_name
                )
        else:
            raise UnsupportedTableType(
                'unsupported table type: ' + str(self.table_type),
                table_name
            )

        try:
            exists_result = self._direct_query(exists_query)
        except Exception as error_msg:
            #TODO logger
            raise error_msg

        if len(exists_result) != 1:
            #TODO logger
            if debug:
                print(
                    '---- TABLE {schema_name}.{table_name} NOT FOUND, creating table'.\
                    format(
                        schema_name=schema_name,
                        table_name =table_name
                    ))
            try:
                self._create_table(self.get_table_create_string())
            except Exception as error_msg:
                raise error_msg

            if debug:
                print(
                    '---- {schema_name}.{table_name} CREATED'.\
                    format(
                        schema_name=schema_name,
                        table_name =table_name
                    ))
        else:
            if debug:
                print(
                    '---- TABLE {schema_name}.{table_name} EXISTS'.\
                    format(
                        schema_name=schema_name,
                        table_name =table_name
                    ))

    def test_table_headers(
            self,
            table_name,
            schema_name,
            defined_headers,
            debug=False,
            logger=None

    ):
        '''test if headers are correctly covered by cfg'''

        header_query = ''
        header_result = False #TODO: remove?
        if self.table_type == TableType.MySQL:
            header_query = \
            '''SELECT `COLUMN_NAME`
                FROM `INFORMATION_SCHEMA`.`COLUMNS`
                WHERE `TABLE_SCHEMA`=\'{schema_name}\'
                AND `TABLE_NAME`=\'{table_name}\''''.\
                format(
                    schema_name=schema_name,
                    table_name =table_name
                )
        else:
            raise UnsupportedTableType(
                'unsupported table type: ' + str(self.table_type),
                table_name
            )

        try:
            headers = self._direct_query(header_query)
        except Exception as error_msg:
            #TODO logger
            raise error_msg
        #TODO mysql specific? vvv
        headers = table_utils.mysql_cleanup_results(headers)

        if debug:
            print(headers)
        if not table_utils.bool_test_headers(
                headers,
                defined_headers,
                debug=debug,
                #logger=Logger #TODO
        ):
            error_msg = 'Table headers not equivalent'
            print(error_msg)
            raise MismatchedHeaders(
                error_msg,
                table_name)

    @abc.abstractmethod
    def get_table_create_string(self):
        '''get/parse table-create file'''
        pass

    def __del__(self):
        '''release connection/cursor'''
        #__del__ needs to be in lowest-child to execute:
        #http://www.electricmonk.nl/log/2008/07/07/python-destructor-and-garbage-collection-notes/
        #FIXME vvv need to close cursor?
        #self._cursor.close()
        self._connection.close()

    #TODO: write helper methods for handling timeseries data

class ConnectionException(Exception):
    '''base class for table-connection exceptions'''
    def __init__(self, message, tablename):
        self.message = message
        self.tablename = tablename

    def __str__(self):
        error_msg = 'CONNECTION EXCEPTION: {tablename}-{message}'.\
        format(
            tablename=self.tablename,
            message=self.message
        )
        return error_msg

class CreateTableError(ConnectionException):
    '''unable to create table (if none existed)'''
    pass

class TableKeysMissing(ConnectionException):
    '''missing keys in config.  Can recreate from db connection...
        but manual listing for easier code for now'''
    pass

class UnsupportedTableType(ConnectionException):
    '''unable to execute command, not supported'''
    pass

class MismatchedHeaders(ConnectionException):
    '''defined headers and table headers do not line up'''
    pass
