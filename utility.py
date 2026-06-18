# import requests
from flask import redirect, render_template, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/")
        return f(*args, **kwargs)

    return decorated_function


def search(string, target):
    pos = None
    for i in range(len(string)):
        if string[i] == target:
            pos = i
            return pos


def gbp(value):
    """Format value as gbp."""
    return f"£{value:,.2f}"


def show_expense(value):
    """Show expense ."""
    return gbp(handle_expense(value))


def handle_expense(expense):
    return float(expense) + (float(expense) * -2)


def get_income(datebase):
    income = datebase.execute(
        "SELECT SUM(amount) AS income FROM transactions WHERE user_id = ?  AND type = 'Income'", session["user_id"])[0]["income"]
    if income == None:
        income = 0.0
    return income


def get_expense(datebase):
    expense = datebase.execute(
        "SELECT SUM(amount) AS expense FROM transactions WHERE user_id = ?  AND type = 'Expense'", session["user_id"])[0]["expense"]
    if expense == None:
        expense = 0.0
    return expense


def get_transactions(datebase, e=""):
    return datebase.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC " + e, session["user_id"])


def get_budgets(datebase):
    rows  = datebase.execute("SELECT name , budgets.amount As [budget] ,  sum(transactions.amount) AS spent  FROM budgets LEFT JOIN transactions ON transactions.user_id = budgets.user_id AND transactions.category = budgets.name WHERE budgets.user_id = ? GROUP BY name , budget ", session["user_id"])
    for row in rows:
        if row["spent"] == None :
            row["spent"] = 0.0
    return rows
