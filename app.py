import os
from io import BytesIO
from PIL import Image
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, send_file
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# Report
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet

# Mine
from utility import login_required, search, gbp, get_expense, get_income, get_transactions, show_expense, handle_expense, get_budgets

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["gbp"] = gbp
app.jinja_env.filters["show_expense"] = show_expense


# category of transactions
CATEGORIES = [
    "Salary",
    "Food",
    "Transport",
    "Shopping",
    "Entertainment",
    "Bills",
    "Health",
    "Education",
    "Other"
]


# type of transactions
TYPES = ["Income", "Expense"]

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///track.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect("/dashboard")
    else:
        return render_template("index.html")


@app.route("/404")
def not_found():
    if session.get("user_id"):
        return render_template("not_found.html", id=session["user_id"])
    else:
        return render_template("not_found.html")


@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","").strip()
        confirm_password = request.form.get("confirmPassword","").strip()

        if not name:
            flash("Name is required", "danger")
            return render_template("/auth/register.html", name=name)

        if not email:
            flash("Email is required", "danger")
            return render_template("/auth/register.html", name=name, email=email)

        if not password:
            flash("Password is required", "danger")
            return render_template("/auth/register.html", name=name, email=email, password=password)
        if not confirm_password:
            flash("Confirmation password is required", "danger")
            return render_template("/auth/register.html", name=name, email=email, password=password, confirm=confirm_password)

        if confirm_password != password:
            flash("Password don't match", "danger")
            return render_template("/auth/register.html", name=name, email=email, password=password, confirm=confirm_password)
        try:
            # add user to database and hash password
            password_hash = generate_password_hash(password)
            username = email[:search(email, '@')]
            rows = db.execute("SELECT  COUNT(*) AS count FROM users WHERE username LIKE ?",
                              f"{username}%")
            if rows[0]["count"] >= 1:
                username = f'{username}{rows[0]["count"] + 1}'
            db.execute("INSERT INTO users (name , email, username , hash) VALUES( ?, ?, ?, ?)",
                       name, email, username, password_hash)
        except ValueError:
            flash("Email already exits  , try to log in", "warning")
            return render_template("/auth/login.html")

        rows = db.execute("SELECT id FROM users WHERE username= ?", username)

        # set session to remember user id
        session["user_id"] = rows[0]["id"]
        flash("Registered successfully", "success")
        del name, email, password, confirm_password
        return redirect("/dashboard")

    else:
        return render_template("/auth/register.html")


@app.route("/login", methods=["POST", "GET"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    if request.method == "POST":
        # get email or username and password
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","").strip()

        if not email:
            flash("Email/Username is required", "danger")
            return render_template("/auth/login.html", email=email)

        if not password:
            flash("Password is required", "danger")
            return render_template("/auth/login.html", email=email, password=password)

        rows = db.execute(
            "SELECT * FROM users WHERE username = ? or email = ? ", email, email)

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            if '@' in email:
                flash("Invalid email or password", "danger")
            else:
                flash("Invalid username or password", "danger")
            return render_template("/auth/login.html", email=email, password=password)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # show a success message and redirect to dashboard
        flash("You were loged in successfully", "success")
        del email, password
        return redirect("/dashboard")
    else:
        return render_template("/auth/login.html")


@app.route("/logout")
@login_required
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    flash("You were loged out successfully", "success")
    return redirect("/")


@app.route("/dashboard")
@login_required
def dashboard():
    income = get_income(db)
    expense = get_expense(db)
    transactions = get_transactions(db, e="LIMIT 10")
    balance = income + expense
    name = db.execute("SELECT name FROM users WHERE id = ? ",
                      session["user_id"])[0]["name"].title()
    rows = db.execute(
        "SELECT category, SUM(amount) AS total FROM transactions WHERE user_id = ? AND type = 'Expense' GROUP BY category", session["user_id"])

    times = db.execute(
        "SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total FROM transactions WHERE user_id = ? AND type = 'Expense' GROUP BY month ORDER BY month", session["user_id"])

    categories = [row["category"] for row in rows]
    amounts = [handle_expense(row["total"]) for row in rows]

    months = [time["month"] for time in times]
    totals = [handle_expense(time["total"]) for time in times]

    return render_template("dashboard.html", balance=balance,
                           income=income, expense=handle_expense(expense), name=name,
                           transactions=transactions, categories=categories, amounts=amounts,
                           months=months, totals=totals
                           )


@app.route("/profile")
@login_required
def profile():
    user = db.execute("SELECT * FROM users WHERE id = ?",
                      session["user_id"])[0]
    income = get_income(db)
    expense = get_expense(db)
    balance = income + expense
    transactions_count = db.execute(
        "SELECT COUNT(*) AS number FROM transactions WHERE user_id = ?", session["user_id"])[0]["number"]

    return render_template("/profile/profile.html", user=user, balance=balance, income=income, expense=expense, transactions_count=transactions_count)


@app.route("/profile/change_password", methods=["POST", "GET"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password","").strip()
        new_password = request.form.get("new_password","").strip()
        confirm_password = request.form.get("confirm_password","").strip()

        if not current_password:
            flash("Current password is required", "danger")
            return render_template("/profile/change_password.html", current=current_password)

        if not new_password:
            flash("New password is required", "danger")
            return render_template("/profile/change_password.html", current=current_password, new=new_password)

        if not confirm_password:
            flash("Confirmation password is required", "danger")
            return render_template("/profile/change_password.html", current=current_password, new=new_password, confirm=confirm_password)
        if new_password != confirm_password:
            flash("Password don't match", "danger")
            return render_template("/profile/change_password.html", current=current_password, new=new_password, confirm=confirm_password)

        rows = db.execute(
            "SELECT hash FROM users WHERE id = ?", session["user_id"])
        if not check_password_hash(rows[0]["hash"], current_password):
            flash("Current password is incorrect", "danger")
            return render_template("/profile/change_password.html", current=current_password, new=new_password, confirm=confirm_password)

        password_hash = generate_password_hash(new_password)
        db.execute("UPDATE users SET hash = ? WHERE id = ? ",
                   password_hash, session["user_id"])
        flash("Password has been updated successfully", "success")
        del current_password, new_password, confirm_password
        return redirect("/profile")

    else:
        return render_template("/profile/change_password.html")


@app.route("/profile/delete", methods=["POST"])
@login_required
def delete():
    db.execute("DELETE FROM transactions WHERE user_id = ?",
               session["user_id"])
    db.execute("DELETE FROM budgets WHERE user_id = ?", session["user_id"])
    db.execute("DELETE FROM users WHERE id = ?", session["user_id"])
    session.clear()
    return redirect("/")


@app.route("/profile/upload_profile_picture", methods=["POST"])
@login_required
def upload_profile_picture():

    # Get image
    file = request.files.get("profile_picture")

    # check if user uploaded an image
    if not file:
        flash("Please choose a file.", "danger")
        return redirect("/profile")

    # check if what user uploaded is an image
    try:
        Image.open(file).verify()
        file.seek(0)
    except Exception:
        flash("Invalid image file.", "danger")
        return redirect("/profile")

    # Get old image path from database
    old_image = db.execute(
        "SELECT profile_picture FROM users WHERE id = ?",
        session["user_id"]
    )[0]["profile_picture"]

    # Delete old image if it exists
    if old_image != "default.png" and os.path.exists(f"static/images/{old_image}"):
        print("Found")
        os.remove(f"static/images/{old_image}")

    # name_image
    filename = f"{session['user_id']}.{secure_filename(file.filename).rsplit('.', 1)[-1].lower()}"

    file.save(f"static/images/{filename}")

    db.execute(
        "UPDATE users SET profile_picture = ? WHERE id = ?",
        filename,
        session["user_id"]
    )

    flash("Profile picture updated.", "success")
    return redirect("/profile")


@app.route("/transactions")
@login_required
def transactions():
    transactions = get_transactions(db)

    return render_template("transactions/transactions.html", transactions=transactions)


@app.route("/transactions/add", methods=["POST", "GET"])
@login_required
def addTransaction():
    if request.method == "POST":

        # get user input
        transaction_type = request.form.get("type", "").strip()
        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date" , "").strip()
        description = request.form.get("description", "").strip()

        # check if type is not empty
        if not transaction_type:
            flash("Type is required.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES, )

        # check if amount is not empty
        if not amount:
            flash("Amount is required.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type)

        # check if category is not empty
        if not category:
            flash("Category is required.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type, amount=amount)

        # check if date is not empty
        if not date:
            flash("Date is required.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type, amount=amount, category=category)

        # check if type not an income or expense
        if not transaction_type in TYPES:
            flash("Invalid type.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type, amount=amount, category=category, date=date,
                                   description=description)

        # check if tamount less than zero
        try:
            amount = float(amount)
        except ValueError:
            flash("Amount must be a number.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type, amount=amount, category=category, date=date,
                                   description=description)

        if amount <= 0:
            flash("Invalid amount , amount must be greater than 0.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type, amount=amount, category=category, date=date,
                                   description=description)

        # check if category not a valid one
        if not category in CATEGORIES:
            flash("Invalid category.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type, amount=amount, category=category, date=date, description=description)

        if transaction_type == "Expense":
            amount = amount * -1

        db.execute(
            "INSERT INTO transactions (user_id, type, category, amount, description, date) VALUES(?, ?, ?, ?, ?, ?)",
            session["user_id"], transaction_type, category, amount, description, date)
        flash("Transaction was added successfully", "success")
        return redirect("/transactions")

    else:
        return render_template("/transactions/add.html", categories=CATEGORIES, types=TYPES)


@app.route("/transactions/delete/<int:id>", methods=["POST"])
@login_required
def deleteTransactions(id):

    db.execute("DELETE FROM transactions WHERE id = ? AND user_id = ? ",
               id, session["user_id"])
    return redirect("/transactions")


@app.route("/transactions/edit/<int:id>", methods=["POST", "GET"])
@login_required
def editTransactions(id):
    if request.method == "POST":
        # get user input
        transaction_type = request.form.get("type", "").strip()
        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date")
        description = request.form.get("description", "").strip()

        # check if type is not empty
        if not transaction_type:
            flash("Type is required.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES, )

        # check if amount is not empty
        if not amount:
            flash("Amount is required.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type)

        # check if category is not empty
        if not category:
            flash("Category is required.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type, amount=amount)

        # check if date is not empty
        if not date:
            flash("Date is required.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type, amount=amount, category=category)

        # check if type not an income or expense
        if not transaction_type in TYPES:
            flash("Invalid type.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type, amount=amount, category=category, date=date,
                                   description=description)

        # check if tamount less than zero
        try:
            amount = float(amount)
        except ValueError:
            flash("Amount must be a number.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type, amount=amount, category=category, date=date,
                                   description=description)

        if amount <= 0:
            flash("Invalid amount , amount must be greater than 0.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type, amount=amount, category=category, date=date,
                                   description=description)

        # check if category not a valid one
        if not category in CATEGORIES:
            flash("Invalid category.", "danger")
            return render_template("/transactions/add.html", types=TYPES, categories=CATEGORIES,
                                   transaction_type=transaction_type, amount=amount, category=category, date=date, description=description)

        if transaction_type == "Expense":
            amount = amount * -1

        db.execute(
            "UPDATE transactions SET type = ?, category = ? , amount = ? , description = ? , date = ?  WHERE id = ? AND user_id  = ?",
            transaction_type, category, amount, description, date, id, session["user_id"])
        flash("Transaction was updated successfully", "success")
        return redirect("/transactions")
    else:
        row = db.execute(
            "SELECT * FROM transactions WHERE user_id = ? AND id = ?", session["user_id"], id)
        if not row:
            return redirect("/404")
        row = row[0]
        amount = handle_expense(
            row["amount"]) if row["type"] == "Expense" else row["amount"]

        return render_template("/transactions/edit.html", types=TYPES, categories=CATEGORIES,
                               transaction_type=row["type"], category=row["category"], amount=amount, date=row["date"], description=row["description"], id=id)


@app.route("/budgets")
@login_required
def budgets():
    budgets = get_budgets(db)
    # spent =  db.execute("SELECT category , SUM(amount) AS spent FROM transactions WHERE user_id = ? AND type = 'Expense' GROUP BY category" , session["user_id"] )
    return render_template("/budgets/budgets.html", budgets=budgets)


@app.route("/budgets/add", methods=["POST", "GET"])
@login_required
def addBudget():
    if request.method == "POST":

        # get budget naem and amount
        name = request.form.get("name" , "").strip()
        amount = request.form.get("amount", "").strip()

        # check budget name is not empty
        if not name:
            flash("Category is required.", "danger")
            return render_template("/budgets/add.html", categories=CATEGORIES)

        # check amount is not empty
        if not amount:
            flash("Budget is required.", "danger")
            return render_template("/budgets/add.html", categories=CATEGORIES, name=name)

        # check if category not a valid one
        if not name in CATEGORIES:
            flash("Invalid category.", "danger")
            return render_template("/budgets/add.html", categories=CATEGORIES, name=name, amount=amount)

         # check if tamount less than zero
        try:
            amount = float(amount)
        except ValueError:
            flash("Budget must be a number.", "danger")
            return render_template("/budgets/add.html", categories=CATEGORIES, name=name, amount=amount)

        if amount <= 0:
            flash("Invalid budget , budget must be greater than 0.", "danger")
            return render_template("/budgets/add.html", categories=CATEGORIES, name=name, amount=amount)
        try:
            db.execute("INSERT INTO budgets (user_id , name , amount) VALUES (?, ?, ?) ",
                       session["user_id"], name, amount)
        except ValueError:
            flash("Buget already exist", "danger")
            return redirect("/budgets")

        flash("Budget was added successfully", "success")
        return redirect("/budgets")

    else:
        return render_template("/budgets/add.html", categories=CATEGORIES)


@app.route("/report", methods=["POST"])
@login_required
def report():

    buffer = BytesIO()

    pdf = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    income = get_income(db)
    expense = get_expense(db)
    balance = income + expense

    content = []

    content.append(Paragraph("Personal Finance Report", styles["Title"]))
    content.append(Spacer(1, 20))

    content.append(
        Paragraph(f"Current Balance : {gbp(balance)}", styles["Normal"]))
    content.append(
        Paragraph(f"Total Income : {gbp(income)}", styles["Normal"]))
    content.append(
        Paragraph(f"Total Expenses : {show_expense(expense)}", styles["Normal"]))

    content.append(Spacer(1, 20))

    content.append(Paragraph("Budget Summary", styles["Heading2"]))

    budgets = get_budgets(db)
    if len(budgets) != 0:
        for budget in budgets:
            content.append(Paragraph(
                f"{budget['name']} : {show_expense(budget['spent'])} / {gbp(budget['budget'])}", styles["Normal"]))
    else:
        content.append(
            Paragraph("You did not add any budget", styles["Normal"]))

    content.append(Spacer(1, 20))

    content.append(Paragraph("Recent Transactions", styles["Heading2"]))
    transactions = get_transactions(db)
    if len(transactions) != 0:

        for transaction in transactions:
            content.append(Paragraph(
                f"{transaction['type']}   |   {transaction['category']}   |   £{transaction['amount']}   |   {transaction['date']}", styles["Normal"]))
    else:
        content.append(
            Paragraph("You did not do any transaction", styles["Normal"]))

    pdf.build(content)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="finance_report.pdf",
        mimetype="application/pdf"
    )


@app.errorhandler(404)
def not_found(error):
    return redirect("/404")

# @app.route("/goals")
# @app.route("/goals/add")
