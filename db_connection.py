import mysql.connector
from mysql.connector import Error
import configparser

def get_connection():
    try:
        # Read config file
        config = configparser.ConfigParser()
        config.read("db_config.ini")

        db_config = {
            "host": config["mysql"]["host"],
            "user": config["mysql"]["user"],
            "password": config["mysql"]["password"],
            "database": config["mysql"]["database"],
            "port": int(config["mysql"]["port"])
        }

        # Create connection
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            print("✅ MySQL connected successfully")
            return connection

    except Error as e:
        print("❌ Error while connecting to MySQL:", e)
        return None
