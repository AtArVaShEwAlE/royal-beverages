"""
Database Adapter - Makes PostgreSQL work with MySQL-style code
No need to change your existing database queries!
"""
from flask import current_app

def get_db():
    """Get the appropriate database connection"""
    if current_app.config.get('USE_POSTGRES', False):
        # PostgreSQL via SQLAlchemy
        return current_app.extensions.get('sqlalchemy')
    else:
        # MySQL
        return current_app.extensions.get('mysql')


def execute_query(query, params=None, fetch='all', commit=False):
    """
    Execute a database query - works with both MySQL and PostgreSQL
    
    Args:
        query: SQL query string
        params: Query parameters (tuple or list)
        fetch: 'all', 'one', or None
        commit: Whether to commit the transaction
        
    Returns:
        Query results (list of dicts for 'all', dict for 'one', None otherwise)
    """
    if current_app.config.get('USE_POSTGRES', False):
        # PostgreSQL
        db = current_app.extensions['sqlalchemy']
        
        # Convert MySQL placeholders (%s) to PostgreSQL (:1, :2, etc.)
        if params:
            pg_query = query
            for i, param in enumerate(params, 1):
                pg_query = pg_query.replace('%s', f':{i}', 1)
            
            # Create parameter dict
            param_dict = {str(i): param for i, param in enumerate(params, 1)}
            result = db.session.execute(db.text(pg_query), param_dict)
        else:
            result = db.session.execute(db.text(query))
        
        if commit:
            db.session.commit()
        
        if fetch == 'all':
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
        elif fetch == 'one':
            row = result.fetchone()
            return dict(row._mapping) if row else None
        else:
            return None
    else:
        # MySQL
        mysql = current_app.extensions['mysql']
        cursor = mysql.connection.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if commit:
            mysql.connection.commit()
        
        if fetch == 'all':
            results = cursor.fetchall()
        elif fetch == 'one':
            results = cursor.fetchone()
        else:
            results = None
        
        cursor.close()
        return results


def get_cursor():
    """
    Get a database cursor for manual operations
    
    Usage:
        cursor = get_cursor()
        cursor.execute("SELECT * FROM users")
        results = cursor.fetchall()
        cursor.close()
    """
    if current_app.config.get('USE_POSTGRES', False):
        # PostgreSQL - return a wrapper that mimics MySQL cursor
        return PostgresCursorWrapper()
    else:
        # MySQL
        mysql = current_app.extensions['mysql']
        return mysql.connection.cursor()


class PostgresCursorWrapper:
    """Wrapper to make PostgreSQL cursor work like MySQL cursor"""
    
    def __init__(self):
        from flask import current_app
        self.db = current_app.extensions['sqlalchemy']
        self.last_result = None
    
    def execute(self, query, params=None):
        """Execute a query"""
        if params:
            # Convert %s to positional parameters
            pg_query = query
            for i in range(len(params)):
                pg_query = pg_query.replace('%s', f':{i+1}', 1)
            
            param_dict = {str(i+1): param for i, param in enumerate(params)}
            self.last_result = self.db.session.execute(self.db.text(pg_query), param_dict)
        else:
            self.last_result = self.db.session.execute(self.db.text(query))
        
        return self.last_result
    
    def fetchall(self):
        """Fetch all results"""
        if self.last_result:
            rows = self.last_result.fetchall()
            return [dict(row._mapping) for row in rows]
        return []
    
    def fetchone(self):
        """Fetch one result"""
        if self.last_result:
            row = self.last_result.fetchone()
            return dict(row._mapping) if row else None
        return None
    
    def close(self):
        """Close cursor (no-op for PostgreSQL)"""
        self.last_result = None


def commit():
    """Commit the current transaction"""
    if current_app.config.get('USE_POSTGRES', False):
        db = current_app.extensions['sqlalchemy']
        db.session.commit()
    else:
        mysql = current_app.extensions['mysql']
        mysql.connection.commit()