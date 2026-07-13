import re
import uuid
from typing import Any
from mcp.server.fastmcp import FastMCP
from ConnectionManager import ConnectionManager

"""SQL Assistant MCP server.

This server exposes a small set of MySQL-focused MCP tools for managing
sessions, creating connections, inspecting schema metadata, and executing
SQL queries. The tools are designed to be called by MCP Inspector and LLM
agents, so each tool has a concise description and typed parameters.
"""

mcp = FastMCP("SQL Assistant")
connectionManager = ConnectionManager()


def _quote_mysql_identifier(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("Identifier must contain only letters, numbers, and underscores")
    return f"`{name}`"

@mcp.tool(description="Start a new logical session and return a session_id used by all other tools.")
def start_session() -> dict[str, Any]:
    """Create a new session id for tracking a database connection.

    Returns:
        A JSON object with a success status and a UUID session_id.
    """
    session_id = str(uuid.uuid4())
    return {
        "status": "success",
        "session_id": session_id
    }

@mcp.tool(description="End a session and close any active database connection for that session.")
def end_session(session_id: str) -> dict[str, str]:
    """Close an active connection for the given session and end the session.

    Args:
        session_id: Session identifier returned by start_session.
    """
    if (connectionManager.get_connection(session_id) and connectionManager.disconnect(session_id)) or connectionManager.get_connection(session_id) is None:
        return {
            "status": "success",
            "message": "Session ended successfully"
        }
    
    return {
        "status": "failure",
        "message": "Failed to disconnect from SQL database server"
    }
   
@mcp.tool(description="Create a new MySQL connection for an existing session.")
def connect_datebase_server(
    session_id: str,
    database_type: str,
    host: str,
    port: int,
    username: str,
    password: str,
    database_name: str | None = None,
) -> dict[str, Any]:
    """Create a MySQL connection and store it under the given session.

    Args:
        session_id: Session identifier returned by start_session.
        database_type: Database backend, currently expected to be 'mysql'.
        host: MySQL host name or IP address.
        port: MySQL TCP port.
        username: MySQL username.
        password: MySQL password.
        database_name: Optional default database to connect to.
    """
    if connectionManager.get_connection(session_id) is not None:
        connectionManager.disconnect(session_id)
    
    return connectionManager.connect(session_id, database_type, host, port, username, password, database_name)
    
@mcp.tool(description="Disconnect the current database connection for a session.")
def disconnect_datebase_server(session_id: str) -> dict[str, str]:
    """Disconnect the active database connection for the provided session."""
    result = connectionManager.disconnect(session_id)
    if result:
        return {
            "status": "success",
            "message": "Disconnected from database successfully."
        }
    
    else:
        return {
            "status": "failure",
            "message": "Something went wrong please check the session id validity"
        }

@mcp.tool(description="Return stored metadata about a session's database connection.")
def get_connection_info(session_id: str) -> dict[str, Any]:
    """Return the recorded connection metadata for a session.

    The result includes connection creation time, host, port, username, and
    the database name supplied during connection.
    """
    connection_info = connectionManager.get_connection_info(session_id)

    if connection_info is None:
        return {
            "status": "failure",
            "message": "No connection info found for this session"
        }

    return {
        "status": "success",
        "connectionInfo": connection_info,
    }

@mcp.tool(description="List all databases visible to the active MySQL connection.")
def list_databases(session_id: str) -> dict[str, Any]:
    """Return all databases available to the active MySQL connection."""
    connection = connectionManager.get_connection(session_id)
    db_type = connectionManager.get_type(session_id)
    
    if connection is None:
        return {
            "status": "failure",
            "message": """No active connection for this session.
            Please run **connect_database_server** tool to create a connection to a sql server"""
        }
    
    if db_type == "mysql":
        try:
            cursor = connection.cursor()
            cursor.execute("SHOW DATABASES;")
            databases = cursor.fetchall()
            cursor.close()
            
            db_list = [db[0] for db in databases]
            return {
                "status": "success",
                "databases": db_list
            }
        except Exception as err:
            return {
                "status": "failure",
                "message": f"Error fetching databases",
                "errorMessage": f"{err}"
            } 

    return {
        "status": "failure",
        "message": f"Unsupported database type: {db_type}"
    }

@mcp.tool(description="Switch the active MySQL connection to a specific database.")
def use_database(session_id: str, database_name: str) -> dict[str, str]:
    """Set the current database on the active MySQL connection.

    Args:
        session_id: Session identifier returned by start_session.
        database_name: Target database name.
    """
    connection = connectionManager.get_connection(session_id)
    db_type = connectionManager.get_type(session_id)
    
    if connection is None:
        return {
            "status": "failure",
            "message": "No active connection for this session"
        }

    if db_type == "mysql":
        try:
            cursor = connection.cursor()
            cursor.execute(f"USE {_quote_mysql_identifier(database_name)};")
            cursor.close()
            
            return {
                "status": "success"
            }
        except Exception as err:
            return {
                "status": "failure",
                "message": f"Error while trying to use the new database: {err}"
            } 

    return {
        "status": "failure",
        "message": f"Unsupported database type: {db_type}"
    }

@mcp.tool(description="Report the currently selected database for the active session.")
def get_current_database(session_id: str) -> dict[str, Any]:
    """Return the database currently selected on the MySQL connection."""
    connection = connectionManager.get_connection(session_id)
    db_type = connectionManager.get_type(session_id)

    if connection is None:
        return {
            "status": "failure",
            "message": "No active connection for this session"
        }
    if db_type == "mysql":
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT DATABASE();")
            database = cursor.fetchone()
            cursor.close()
            return {
                "status": "success",
                "database": database[0] if database and database[0] else None,
            }
            
        except Exception as err:
            return {
                "status": "failure",
                "message": "Error while trying to get the currently used database",
                "errorMessage": f"{err}"
            }

    return {
        "status": "failure",
        "message": f"Unsupported database type: {db_type}"
    }
        
@mcp.tool(description="List tables in the active database or in a database passed explicitly.")
def list_tables(session_id: str, database_name: str | None = None) -> dict[str, Any]:
    """Return the tables visible in the selected or provided database.

    Args:
        session_id: Session identifier returned by start_session.
        database_name: Optional database name to switch to before listing tables.
    """
    connection = connectionManager.get_connection(session_id)
    db_type = connectionManager.get_type(session_id)
    
    if connection is None:
        return {
            "status": "failure",
            "message": "No active connection for this session"
        }

    if db_type == "mysql":
        try:
            cursor = connection.cursor()
            if database_name is not None:
                cursor.execute(f"USE {_quote_mysql_identifier(database_name)}")
            cursor.execute(f"SHOW TABLES;")
            tables = cursor.fetchall()
            cursor.close()
            
            tables_list = [table[0] for table in tables]

            return {
                "status": "success",
                "tables": tables_list
            }
        except Exception as err:
            return {
                "status": "failure",
                "message": f"Error while trying to use the new database",
                "errorMessage": f"{err}"
            }

    return {
        "status": "failure",
        "message": f"Unsupported database type: {db_type}"
    }

@mcp.tool(description="Describe the columns, types, and keys for a table.")
def table_schema(session_id: str, table_name: str,database_name: str | None = None) -> dict[str, Any]:
    """Return the schema for a table in the current or provided database.

    Args:
        session_id: Session identifier returned by start_session.
        table_name: Table to inspect.
        database_name: Optional database to use before describing the table.
    """
    connection = connectionManager.get_connection(session_id)
    db_type = connectionManager.get_type(session_id)
    
    if connection is None:
        return {
            "status": "failure",
            "message": "No active connection for this session"
        }

    if db_type == "mysql":
        try:
            cursor = connection.cursor()
            effective_database_name = database_name
            if effective_database_name is not None:
                cursor.execute(f"USE {_quote_mysql_identifier(effective_database_name)};")
            else:
                cursor.execute("SELECT DATABASE();")
                current_database = cursor.fetchone()
                effective_database_name = current_database[0] if current_database and current_database[0] else None

            if effective_database_name is None:
                cursor.close()
                return {
                    "status": "failure",
                    "message": "No database is selected for this connection",
                }

            cursor.execute(f"DESCRIBE {_quote_mysql_identifier(table_name)};")
            schema = list(cursor.fetchall())
            cursor.close()
            
            result = [
                {
                    "column name": column[0],
                    "data type": column[1],
                    "null allowed": column[2],
                    "key type": column[3],
                    "default value": column[4],
                    "extra information": column[5] if column[5] else None,
                }
                for column in schema
            ]

            return {
                "status": "success",
                "table schema": result
            }
        except Exception as err:
            return {
                "status": "failure",
                "message": f"Error while trying to use the new database: {err}"
            }

    return {
        "status": "failure",
        "message": f"Unsupported database type: {db_type}"
    }

@mcp.tool(description="Return foreign key metadata for a table.")
def get_foreign_keys(session_id: str, table_name: str, database_name: str | None = None) -> dict[str, Any]:
    """Return foreign key relationships for a table.

    Args:
        session_id: Session identifier returned by start_session.
        table_name: Table to inspect.
        database_name: Optional database name; if omitted the active database is used.
    """
    connection = connectionManager.get_connection(session_id)
    db_type = connectionManager.get_type(session_id)
    
    if connection is None:
        return {
            "status": "failure",
            "message": "No active connection for this session"
        }
    
    if db_type == "mysql":
        try:
            cursor = connection.cursor()
            effective_database_name = database_name
            if effective_database_name is None:
                cursor.execute("SELECT DATABASE();")
                current_database = cursor.fetchone()
                effective_database_name = current_database[0] if current_database and current_database[0] else None

            if effective_database_name is None:
                cursor.close()
                return {
                    "status": "failure",
                    "message": "No database is selected for this connection",
                }

            cursor.execute(
                """
                SELECT
                    TABLE_NAME,
                    COLUMN_NAME,
                    CONSTRAINT_NAME,
                    REFERENCED_TABLE_NAME,
                    REFERENCED_COLUMN_NAME
                FROM
                    information_schema.KEY_COLUMN_USAGE
                WHERE
                    TABLE_SCHEMA = %s
                    AND TABLE_NAME = %s
                    AND REFERENCED_TABLE_NAME IS NOT NULL;
                """,
                (effective_database_name, table_name)
            )
            foreign_keys = [
                {
                    "table name": row[0],
                    "column name": row[1],
                    "constraint name": row[2],
                    "referenced table name": row[3],
                    "referenced column name": row[4],
                }
                for row in cursor.fetchall()
            ]
            cursor.close()

            return {
                "status": "success",
                "foreign keys": foreign_keys
            }
        except Exception as err:
            return {
                "status": "failure",
                "message": f"Error while trying to fetch foreign keys: {err}"
            }

    return {
        "status": "failure",
        "message": f"Unsupported database type: {db_type}"
    }

@mcp.tool(description="Return the primary key columns for a table.")
def get_primary_key(session_id: str, table_name: str, database_name: str | None = None) -> dict[str, Any]:
    """Return primary key column metadata for a table.

    Args:
        session_id: Session identifier returned by start_session.
        table_name: Table to inspect.
        database_name: Optional database name; if omitted the active database is used.
    """
    connection = connectionManager.get_connection(session_id)
    db_type = connectionManager.get_type(session_id)
    
    if connection is None:
        return {
            "status": "failure",
            "message": "No active connection for this session"
        }
    
    if db_type == "mysql":
        try:
            cursor = connection.cursor()
            effective_database_name = database_name
            if effective_database_name is None:
                cursor.execute("SELECT DATABASE();")
                current_database = cursor.fetchone()
                effective_database_name = current_database[0] if current_database and current_database[0] else None

            if effective_database_name is None:
                cursor.close()
                return {
                    "status": "failure",
                    "message": "No database is selected for this connection",
                }

            cursor.execute(
                """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s
                AND TABLE_NAME = %s
                AND CONSTRAINT_NAME = 'PRIMARY'
                ORDER BY ORDINAL_POSITION;
                """,
                (effective_database_name, table_name)
            )
            primary_key = [
                {
                    "column name": row[0]
                }
                for row in cursor.fetchall()
            ]
            cursor.close()

            return {
                "status": "success",
                "primary key columns": primary_key
            }
        except Exception as err:
            return {
                "status": "failure",
                "message": f"Error while trying to fetch foreign keys: {err}"
            }

    return {
        "status": "failure",
        "message": f"Unsupported database type: {db_type}"
    }

@mcp.tool(description="Execute a SQL query against the active MySQL connection.")
def execute_query(session_id: str, sql_query: str) -> dict[str,Any]:
    """Execute an arbitrary SQL query and return the result set.

    Args:
        session_id: Session identifier returned by start_session.
        sql_query: SQL statement to execute.
    """
    connection = connectionManager.get_connection(session_id)
    db_type = connectionManager.get_type(session_id)
    
    if connection is None:
        return {
            "status": "failure",
            "message": "No active connection for this session"
        }

    if db_type == "mysql":
        try:
            cursor = connection.cursor()
            cursor.execute(sql_query)
            result = cursor.fetchall()
            cursor.close()

            return {
                "status": "success",
                "message": "SQL query was executed successfully",
                "result": result
            }

        except Exception as err:
            return {
                "status": "failure",
                "message": f"An error occured while executing the SQL query:\n{sql_query}",
                "errorMessage": f"{err}"
            }

    return {
        "status": "failure",
        "message": f"Unsupported database type: {db_type}"
    }
    
if __name__ == "__main__":
    mcp.run(transport="stdio")