
from ..common import consts
from .db import AbstractDB

class MySQLDB(AbstractDB):
    def __init__(self):
        AbstractDB.__init__(self)
        self.db_type = consts.MYSQL
        self.FIELD_TYPES = {
            consts.INTEGER: 'INT',
            consts.TEXT: 'VARCHAR',
            consts.FLOAT: 'DOUBLE',
            consts.CURRENCY: 'DOUBLE',
            consts.DATE: 'DATE',
            consts.DATETIME: 'DATETIME',
            consts.BOOLEAN: 'INT',
            consts.LONGTEXT: 'LONGTEXT',
            consts.KEYS: 'TEXT',
            consts.FILE: 'VARCHAR(512)',
            consts.IMAGE: 'VARCHAR(256)'
        }

    def get_params(self, lib):
        params = self.params
        params['name'] = 'MYSQL'
        params['lib'] = ['MySQLdb', 'mysql.connector']
        params['login'] = True
        params['password'] = True
        params['encoding'] = True
        params['host'] = True
        params['port'] = True
        return params

    def get_lastrowid(self, cursor):
        return cursor.lastrowid

    def get_select(self, query, fields_clause, from_clause, where_clause, group_clause, order_clause, fields):
        start = fields_clause
        end = ''.join([from_clause, where_clause, group_clause, order_clause])
        offset = query.offset
        limit = query.limit
        result = 'SELECT %s FROM %s' % (start, end)
        if limit:
            result += ' LIMIT %d, %d' % (offset, limit)
        return result

    def cast_date(self, date_str):
        return "'" + date_str + "'"

    def cast_datetime(self, datetime_str):
        return "'" + datetime_str + "'"

    def value_literal(self, index):
        return '%s'

    def convert_like(self, field_name, val, data_type):
        return field_name, val

    def create_table(self, table_name, fields, gen_name=None, foreign_fields=None):
        result = []
        primary_key = ''
        sql = 'CREATE TABLE "%s"\n(\n' % table_name
        lines = []
        for field in fields:
            default_text = self.default_text(field)
            line = '"%s" %s' % (field.field_name, self.FIELD_TYPES[field.data_type])
            if field.size != 0 and field.data_type == consts.TEXT:
                line += '(%d)' % field.size
            if field.primary_key:
                line += ' NOT NULL AUTO_INCREMENT'
                primary_key = field.field_name
            elif field.not_null:
                line += ' NOT NULL'
            if not default_text is None:
                line += ' DEFAULT %s' % default_text
            lines.append(line)
        if primary_key:
            lines.append('PRIMARY KEY("%s")' % primary_key)
        sql += ',\n'.join(lines)
        sql += ')\n'
        return sql

    def drop_table(self, table_name, gen_name):
        return 'DROP TABLE IF EXISTS "%s"' % table_name

    def add_field(self, table_name, field):
        line = 'ALTER TABLE "%s" ADD "%s" %s' % \
            (table_name, field.field_name, self.FIELD_TYPES[field.data_type])
        if field.size:
            line += '(%d)' % field.size
        if field.not_null:
            line += ' NOT NULL'
        default_text = self.default_text(field)
        if not default_text is None:
            line += ' DEFAULT %s' % default_text
        return line

    def del_field(self, table_name, field):
        return 'ALTER TABLE "%s" DROP "%s"' % (table_name, field.field_name)

    def change_field(self, table_name, old_field, new_field):
        result = []
        if old_field.not_null != new_field.not_null:
            if new_field.not_null:
                default_value = self.default_value(new_field)
                sql = 'UPDATE "%s" SET "%s" = %s WHERE "%s" IS NULL' % \
                    (table_name, old_field.field_name, default_value, old_field.field_name)
                result.append(sql)
        field_info = self.get_field_info(old_field.field_name, table_name, self.app.admin.task_db_info.database)
        sql = 'ALTER TABLE "%s" CHANGE  "%s" "%s" %s' % (table_name, old_field.field_name,
            new_field.field_name, field_info['data_type'])
        size = field_info['size']
        if size and field_info['data_type'].upper() in ['VARCHAR', 'CHAR', 'BINARY', 'VARBINARY']:
            if new_field.size > size:
                size = new_field.size
            sql += '(%d)' % size
        if new_field.not_null:
            sql += ' NOT NULL'
        default_text = self.default_text(new_field)
        if not default_text is None:
            line += ' DEFAULT %s' % default_text
        elif not field_info['default_value'] is None:
            line += ' DEFAULT %s' % field_info['default_value']
        result.append(sql)
        return result

    def create_index(self, index_name, table_name, unique, fields, desc):
        return 'CREATE %s INDEX "%s" ON "%s" (%s)' % (unique, index_name, table_name, fields)

    def create_foreign_index(self, table_name, index_name, key, ref, primary_key):
        return 'ALTER TABLE "%s" ADD CONSTRAINT "%s" FOREIGN KEY ("%s") REFERENCES "%s"("%s")' % \
            (table_name, index_name, key, ref, primary_key)

    def drop_index(self, table_name, index_name):
        return 'DROP INDEX "%s" ON "%s"' % (index_name, table_name)

    def drop_foreign_index(self, table_name, index_name):
        return 'ALTER TABLE "%s" DROP FOREIGN KEY "%s"' % (table_name, index_name)

    def after_insert(self, cursor, pk_field):
        if pk_field and not pk_field.data:
            pk_field.data = cursor.lastrowid

    def identifier_case(self, name):
        return name.lower()

    def get_table_names(self, connection):
        cursor = connection.cursor()
        cursor.execute('show tables')
        result = cursor.fetchall()
        return [r[0] for r in result]

    def get_table_info(self, connection, table_name, db_name):
        cursor = connection.cursor()
        sql = 'SHOW COLUMNS FROM "%s" FROM %s' % (table_name, db_name)
        cursor.execute(sql)
        result = cursor.fetchall()
        fields = []
        for (field_name, type_size, null, key, default_value, autoinc) in result:
            try:
                pk = False
                if autoinc and key == 'PRI':
                    pk = True
                data_type = type_size.split('(')[0].upper()
                size = type_size.split('(')[1].split(')')[0]
                if size:
                    size = int(size)
                if not data_type in ['VARCHAR', 'CHAR']:
                    size = 0
            except:
                data_type = type_size
                size = 0
            fields.append({
                'field_name': field_name,
                'data_type': data_type,
                'size': size,
                'default_value': default_value,
                'pk': pk,
                'not_null': null == 'NO'
            })
        return {'fields': fields, 'field_types': self.FIELD_TYPES}

db = MySQLDB()
