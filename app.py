from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key'
login_manager = LoginManager()
login_manager.init_app(app)

# Database connection
def get_db_connection():
    conn = mysql.connector.connect(
        host='localhost',
        user='project',
        password='project',
        database='jewellery'
    )
    return conn

# User class
class User:
    def __init__(self, id, username, role_id):
        self.id = id
        self.username = username
        self.role_id = role_id

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return User(user['id'], user['username'], user['role_id'])
    return None

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        role_id = 2  # Default to customer role
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, password, role_id) VALUES (%s, %s, %s)',
                           (username, hashed_password, role_id))
            conn.commit()
            flash('User registered successfully')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            flash('Username already exists')
            return redirect(url_for('register'))
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user and check_password_hash(user['password'], password):
            user_obj = User(user['id'], user['username'], user['role_id'])
            login_user(user_obj)
            if user_obj.role_id == 1:
                return redirect(url_for('admin_index'))
            else:
                return redirect(url_for('customer_index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin_index():
    if current_user.role_id != 1:
        return redirect(url_for('customer_index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM products')
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_index.html', products=products)

@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if current_user.role_id != 1:
        return redirect(url_for('customer_index'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        quantity = request.form['quantity']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO products (name, description, price, quantity) VALUES (%s, %s, %s, %s)',
                       (name, description, price, quantity))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_index'))
    return render_template('add_product.html')

@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    if current_user.role_id != 1:
        return redirect(url_for('customer_index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM products WHERE id = %s', (id,))
    product = cursor.fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        quantity = request.form['quantity']
        
        cursor.execute('UPDATE products SET name = %s, description = %s, price = %s, quantity = %s WHERE id = %s',
                       (name, description, price, quantity, id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_index'))
    cursor.close()
    conn.close()
    return render_template('edit_product.html', product=product)

@app.route('/delete_product/<int:id>', methods=['POST'])
@login_required
def delete_product(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Delete the product
        cursor.execute('DELETE FROM products WHERE id = %s', (id,))
        conn.commit()

        # Re-sequence the product IDs
        cursor.execute('SET @count = 0')
        cursor.execute('UPDATE products SET id = @count:= @count + 1')
        conn.commit()

        # Update the sales table with new product IDs
        cursor.execute('SELECT id FROM products ORDER BY id')
        product_ids = cursor.fetchall()

        for new_id, product in enumerate(product_ids, start=1):
            cursor.execute('UPDATE sales SET product_id = %s WHERE product_id = %s', (new_id, product['id']))
        
        conn.commit()
        flash('Product deleted and IDs re-sequenced successfully.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting product: {str(e)}', 'danger')
    finally:
        cursor.close()

    return redirect(url_for('admin_index'))


@app.route('/sales')
@login_required
def sales():
    if current_user.role_id != 1:
        return redirect(url_for('customer_index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
         SELECT sales.id, products.name, sales.quantity, sales.sale_date, users.username
        FROM sales
        JOIN products ON sales.product_id = products.id
        JOIN users ON sales.user_id = users.id
        ORDER BY sales.id
    ''')
    sales = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('sales.html', sales=sales)

@app.route('/customer')
@login_required
def customer_index():
    if current_user.role_id != 2:
        return redirect(url_for('admin_index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM products WHERE quantity > 0')
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('customer_index.html', products=products)

@app.route('/buy_product/<int:product_id>', methods=['POST'])
@login_required
def buy_product(product_id):
    if current_user.role_id != 2:
        return redirect(url_for('admin_index'))
    
    quantity = int(request.form['quantity'])
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM products WHERE id = %s', (product_id,))
    product = cursor.fetchone()
    print(int(product['price']))
    if product and product['quantity'] >= quantity:
        cursor.execute('INSERT INTO sales (user_id, product_id, quantity,total_price,sale_date) VALUES (%s, %s, %s,%s,NOw())',
                       (current_user.id, product_id, quantity,int(product['price'])*quantity))
        cursor.execute('UPDATE products SET quantity = quantity - %s WHERE id = %s',
                       (quantity, product_id))
        conn.commit()
    
    cursor.close()
    conn.close()
    return redirect(url_for('customer_index'))

@app.route('/my_purchases')
@login_required
def my_purchases():
    if current_user.role_id != 2:
        return redirect(url_for('admin_index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT p.name, s.total_price, s.quantity, s.sale_date
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.user_id = %s
        ORDER BY s.sale_date        
    ''', (current_user.id,))
    purchases = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('my_purchases.html', purchases=purchases)

if __name__ == '__main__':
    app.run(debug=True)
