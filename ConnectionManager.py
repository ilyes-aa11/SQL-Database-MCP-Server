import mysql.connector
import sys
from datetime import datetime, timezone

class ConnectionManager:
    def __init__(self):
        self._connections = dict()
        self._type = dict()
        self._connection_info = dict()

    def connect(self,session_id,db,host,port,username,password,database = None):
        if db == "mysql":
            try:
                if database:
                    connection = mysql.connector.connect(
                        host=host,
                        port=port,
                        user=username,
                        password=password,
                        database=database
                    )
                else:
                    connection = mysql.connector.connect(
                        host=host,
                        port=port,
                        user=username,
                        password=password
                    )
                self._connections[session_id] = connection
                self._type[session_id] = db
                self._connection_info[session_id] = {
                    "database_type": db,
                    "host": host,
                    "port": port,
                    "username": username,
                    "database_name": database,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                return {
                    "status": "success",
                    "message": "Connection created successfully"
                }
            except mysql.connector.Error as err:
                print(f"Error connecting to MySQL: {err}",sys.stderr)
                return {
                    "status": "failure",
                    "message": "An Error has occured",
                    "errorMessage": f"{err}"
                }
        else:
            return False

    def get_connection(self,session_id):
        return self._connections.get(session_id)
    
    def get_type(self,session_id) -> str:
        return self._type.get(session_id)

    def get_connection_info(self, session_id):
        return self._connection_info.get(session_id)

    def disconnect(self,session_id):
        connection = self._connections.get(session_id)
        if not connection:
            return False
        
        db_type = self._type.get(session_id)
        
        try:
            if db_type == "mysql":
                connection.close()
            # Add other database types here in the future
            else:
                print(f"Unknown database type: {db_type}",sys.stderr)
                return False
            
            del self._connections[session_id]
            del self._type[session_id]
            self._connection_info.pop(session_id, None)
            return True
        except mysql.connector.Error as err:
            print(f"Error disconnecting from {db_type}: {err}",sys.stderr)
            return False
        except Exception as err:
            print(f"Unexpected error disconnecting: {err}",sys.stderr)
            return False

    def disconnect_all(self):
        for session in list(self._connections.keys()):
            self.disconnect(session)

    # def execute_sql_query(self,session_id,query):
    #     connection = self.get_connection(session_id)
    #     db_type = self.get_type(session_id)

    #     if connection is None:
    #         raise ValueError("No active connection for this session")
        
    #     if db_type == "mysql":
