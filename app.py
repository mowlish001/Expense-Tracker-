from flask import Flask, render_template, request, redirect, session, url_for
from flask_mysqldb import MySQL
from decimal import Decimal
import MySQLdb.cursors 
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

# ---------- MySQL CONFIG ----------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '010803'
app.config['MYSQL_DB'] = 'expence_tracker'

mysql = MySQL(app)

# ---------------- AUTH -----------------

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['name'] = user[1]
            return redirect(url_for('dashboard'))

        return "Invalid Login"

    return render_template('login.html', page_title="Login")

@app.route('/register', methods=['GET', 'POST'])
def register():
    message = ""  # message to show to user
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        monthly_income = request.form['monthly_income']

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Check if email already exists
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        existing_user = cur.fetchone()

        if existing_user:
            message = "User with this email already exists!"
        else:
            cur.execute(
                "INSERT INTO users (name, email, password, monthly_income) VALUES (%s, %s, %s, %s)",
                (name, email, password, monthly_income)
            )
            mysql.connection.commit()
            return redirect(url_for('login'))

    return render_template('register.html', message=message , page_title="Register")



@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    category = request.args.get('category')  # from dropdown
    start = request.args.get('start')        # from date input
    end = request.args.get('end')            # to date input

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Convert strings to date objects (optional, ensures proper format)
    from datetime import datetime
    if start:
        start = datetime.strptime(start, "%Y-%m-%d").date()
    if end:
        end = datetime.strptime(end, "%Y-%m-%d").date()

    query = "SELECT * FROM expenses WHERE user_id=%s"
    params = [session['user_id']]

    if category and category != 'All':
        query += " AND category=%s"
        params.append(category)

    if start and end:
        query += " AND DATE(expense_date) BETWEEN %s AND %s"
        params.extend([start, end])
    elif start:
        query += " AND DATE(expense_date) >= %s"
        params.append(start)
    elif end:
        query += " AND DATE(expense_date) <= %s"
        params.append(end)

    query += " ORDER BY expense_date DESC"  # Show latest expenses first

    cur.execute(query, params)
    expenses = cur.fetchall()

    total_query = "SELECT IFNULL(SUM(amount),0) as total FROM expenses WHERE user_id=%s"
    total_params = [session['user_id']]

    if category and category != 'All':
        total_query += " AND category=%s"
        total_params.append(category)

    if start and end:
        total_query += " AND DATE(expense_date) BETWEEN %s AND %s"
        total_params.extend([start, end])
    elif start:
        total_query += " AND DATE(expense_date) >= %s"
        total_params.append(start)
    elif end:
        total_query += " AND DATE(expense_date) <= %s"
        total_params.append(end)

    cur.execute(total_query, total_params)
    total_expense = cur.fetchone()['total']

    cur.execute("SELECT DISTINCT category FROM expenses WHERE user_id=%s", (session['user_id'],))
    categories = cur.fetchall()

    
    cur.execute("SELECT name, email, monthly_income, profile_photo FROM users WHERE id=%s", (session['user_id'],))
    user = cur.fetchone()

    monthly_income = float(user['monthly_income'])
    total_expense = float(total_expense)
    money_left = monthly_income - total_expense
    is_exceeded = money_left < 0

    return render_template(
        'dashboard.html',
        expenses=expenses,
        name=session['name'],
        total_expense=total_expense,
        categories=categories,
        selected_category=category,
        user=user,
        money_left=abs(money_left),
        is_exceeded=is_exceeded,
        start=start,
        end=end,
        page_title="Dashboard"
    )


@app.route('/user_info', methods=['GET', 'POST'])
def user_info():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    user = cur.fetchone()

    # Edit mode (view vs edit)
    edit_mode = request.args.get('edit', '0') == '1'

    # Handle POST (Save changes)
    if request.method == 'POST':
        name = request.form['name']
        monthly_income = request.form['monthly_income']

        cur.execute(
            "UPDATE users SET name=%s, monthly_income=%s WHERE id=%s",
            (name, monthly_income, session['user_id'])
        )
        mysql.connection.commit()
        session['name'] = name

        return redirect(url_for('user_info'))

    # Fetch total expenses
    cur.execute(
        "SELECT IFNULL(SUM(amount),0) AS total FROM expenses WHERE user_id=%s",
        (session['user_id'],)
    )
    total_expense = cur.fetchone()['total']

    # ---- Budget Calculation ----
    monthly_income = float(user['monthly_income'])  # Convert Decimal to float
    total_expense = float(total_expense)            # Ensure float
    money_left = monthly_income - total_expense
    is_exceeded = money_left < 0

    return render_template(
        'user_info.html',
        user=user,
        total_expense=total_expense,
        money_left=abs(money_left),
        is_exceeded=is_exceeded,
        edit_mode=edit_mode,
        page_title="User Info"
    )


# ---------------- EXPENSE CRUD -----------------
@app.route('/add', methods=['GET', 'POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        category = request.form['category']

        if category == 'Other':
            category = request.form['other']

        amount = request.form['amount']
        expense_date = request.form['expense_date']  

        cur = mysql.connection.cursor()
        cur.execute(
            """
            INSERT INTO expenses (user_id, title, category, amount, expense_date)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (session['user_id'], title, category, amount, expense_date)
        )
        mysql.connection.commit()

        return redirect(url_for('dashboard'))

    return render_template('add_expense.html')

import MySQLdb.cursors  

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_expense(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        title = request.form['title']
        category = request.form['category']
        amount = request.form['amount']
        expense_date = request.form['expense_date']

        cur.execute(
            """
            UPDATE expenses
            SET title=%s, category=%s, amount=%s, expense_date=%s
            WHERE id=%s AND user_id=%s
            """,
            (title, category, amount, expense_date, id, session['user_id'])
        )
        mysql.connection.commit()

        return redirect(url_for('dashboard'))

    cur.execute(
        "SELECT * FROM expenses WHERE id=%s AND user_id=%s",
        (id, session['user_id'])
    )
    expense = cur.fetchone()

    return render_template('edit_expense.html', expense=expense)


@app.route('/delete/<int:id>')
def delete_expense(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute(
        "DELETE FROM expenses WHERE id=%s AND user_id=%s",
        (id, session['user_id'])
    )
    mysql.connection.commit()

    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True)
