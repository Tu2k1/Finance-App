import os
import string
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]

    user_transactions_db = db.execute(
        "SELECT symbol,name,SUM(shares) AS shares,price FROM transactions WHERE user_id = ? AND trans_type=? GROUP BY symbol ",
        user_id, "bought")
    print(user_transactions_db)
    sold_shares_db = db.execute(
        "SELECT SUM(shares) AS shares,symbol FROM transactions WHERE user_id=? AND trans_type=? GROUP BY symbol",
        user_id, "sold")

    i = 0
    while i < len(user_transactions_db):
        print(i)
        for sold in sold_shares_db:
            if sold["symbol"] == user_transactions_db[i]["symbol"]:
                user_transactions_db[i]["shares"] -= sold["shares"]
                if user_transactions_db[i]["shares"] == 0:
                    del user_transactions_db[i]
                    i -= 1
                    break
        i += 1

    print(user_transactions_db)

    user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    user_cash = user_cash_db[0]["cash"]
    formatted_cash = "${:,.2f}".format(user_cash)

    return render_template("index.html", trans_db=user_transactions_db, cash=formatted_cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if not symbol:
            return apology("must provide a symbol")

        stock = lookup(symbol)

        if stock == None:
            return apology("symbol does not exists")

        if not shares:
            return apology("must provide shares")

        try:
            shares = int(shares)
        except:
            return apology("must provide numbers only in shares")

        if shares < 0:
            return apology("shares cannot be negative")

        transaction = shares * stock["price"]

        user_id = session["user_id"]

        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)

        user_cash = user_cash_db[0]["cash"]

        if user_cash < transaction:
            return apology("not enough cash")

        updated_cash = user_cash - transaction

        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_cash, user_id)

        now = datetime.datetime.now()

        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price, date, name, trans_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
            user_id, stock["symbol"], shares, stock["price"], now, stock["name"], "bought")

        flash("Bought!")

        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]

    transactions_db = db.execute("SELECT * FROM transactions WHERE user_id = ?", user_id)

    return render_template("history.html", database=transactions_db)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/login")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    else:
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("must provide a symbol")

        stock = lookup(symbol)

        if stock == None:
            return apology("symbol does not exists")
        print(stock)
        return render_template("quoted.html", name=stock["name"], price=stock["price"], symbol=stock["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via GET
    if request.method == "GET":
        return render_template("register.html")

    # User reached route via POST
    else:
        # Gets informations from form
        user = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # check if user is empty
        if not user:
            return apology("must provide username")

        # check if password is empty
        if not password:
            return apology("must provide password")

        # # check if confirmation is empty
        if not confirmation:
            return apology("must provide confirmation password")

        # check if password equal confirmation
        if password != confirmation:
            return apology("password and confirmation do not match")

        # personal touch

        # check if password is short
        if len(password) < 8:
            return apology("password is too short")

        # check if the password contains at least one letter, one number and one punctuation
        if not password.isalnum or not any(char in string.punctuation for char in password):
            return apology("password must contains at least one letter, one number and one punctuation")

        # generate a hash for the password
        passwordhash = generate_password_hash(password)

        try:
            newuser = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", user, passwordhash)
        except:
            return apology("username already exists")

        # remember the user
        session["user_id"] = newuser

        # redirect to homepage
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]

    if request.method == "GET":
        user_transactions_db = db.execute(
            "SELECT symbol,SUM(shares) AS shares FROM transactions WHERE user_id = ? AND trans_type=? GROUP BY symbol ",
            user_id, "bought")
        print(user_transactions_db)
        sold_shares_db = db.execute(
            "SELECT SUM(shares) AS shares,symbol FROM transactions WHERE user_id=? AND trans_type=? GROUP BY symbol",
            user_id, "sold")

        i = 0
        while i < len(user_transactions_db):
            print(i)
            for sold in sold_shares_db:
                if sold["symbol"] == user_transactions_db[i]["symbol"]:
                    user_transactions_db[i]["shares"] -= sold["shares"]
                    if user_transactions_db[i]["shares"] == 0:
                        del user_transactions_db[i]
                        i -= 1
                        break
            i += 1

        return render_template("sell.html", symbols=[row["symbol"] for row in user_transactions_db])

    else:
        choosen_symbol = request.form.get("symbol")
        given_shares = request.form.get("shares")

        if not choosen_symbol:
            return apology("must provide symbol")
        if not given_shares:
            return apology("must provide shares")

        given_shares = int(given_shares)

        if given_shares < 0:
            return apology("shares cannot be negative")

        bought_shares_db = db.execute(
            "SELECT SUM(shares) AS shares FROM transactions WHERE user_id=? AND symbol=? AND trans_type=?", user_id,
            choosen_symbol, "bought")
        sold_shares_db = db.execute(
            "SELECT SUM(shares) AS shares FROM transactions WHERE user_id=? AND symbol=? AND trans_type=?", user_id,
            choosen_symbol, "sold")

        bought_shares = 0 if bought_shares_db[0]["shares"] is None else bought_shares_db[0]["shares"]
        sold_shares = 0 if sold_shares_db[0]["shares"] is None else sold_shares_db[0]["shares"]
        shares = bought_shares - sold_shares

        if given_shares > shares:
            return apology("not enough shares")

        stock = lookup(choosen_symbol)

        transaction = given_shares * stock["price"]

        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)

        user_cash = user_cash_db[0]["cash"]

        user_cash += transaction

        db.execute("UPDATE users SET cash = ? WHERE id = ?", user_cash, user_id)

        now = datetime.datetime.now()

        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price, date, name, trans_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
            user_id, stock["symbol"], given_shares, stock["price"], now, stock["name"], "sold")

        flash("Sold!")

        return redirect("/")
