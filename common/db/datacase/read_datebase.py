import pymysql
from contect_db import db_session
from sqlalchemy import text


def execute_query(sql, param=None):
    with db_session() as session:
        result = session.execute(text(sql), {})
        return result.fetchall()


if __name__ == '__main__':
    rows = execute_query("select * from opts.t_data_trade_flow where trade_order_no in('ON25092413433922406977565284284')")
    print(rows)

#
# def read_data_from_trade(host, port, user, pwd, charset, db, sql, sql_value= None):
#     '''
#     读取数据库中的内容
#     :param host:
#     :param port:
#     :param user:
#     :param pwd:
#     :param charset:
#     :param db:
#     :param sql:
#     :param sql_value:
#     :return:
#     '''
#     try:
#         database_list = []
#         db = pymysql.connect(host=host, port=port, user=user, password=pwd, charset=charset, db=db)
#         cursor = db.cursor()
#         if sql_value == None:
#             cursor.execute(sql)
#         else:
#             cursor.execute(sql, sql_value)
#         for data in cursor.fetchall():
#             database_list.append(list(data))
#         return database_list
#     except:
#         return '数据库查询异常'
