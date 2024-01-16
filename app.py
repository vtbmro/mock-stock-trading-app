import os
from datetime import date

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# get current time as a string to build a history
from datetime import datetime

now = datetime.now()
timeoftransaction = now.strftime("%d/%m/%Y %H:%M:%S")

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


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
    if request.method == "POST":
        return redirect("/")

    else:
        # Stock
        # Number of shares
        stocks = db.execute("SELECT symbol,shares FROM portfolio WHERE user_id = %i" % session["user_id"])

        for i in range(len(stocks)):

            temp = lookup(stocks[i]["symbol"])

            # Price of stock (look up symbol)
            stocks[i]["price"] = temp["price"]

            # Total value of holding (shares * lookup(symbol))
            stocks[i]["holding"] = round(stocks[i]["shares"] * stocks[i]["price"], 2)

        # TODO: Missing current cash balance (all total value of holdings + cash)

        totalcash = 0

        for i in range(len(stocks)):
            totalcash += int(stocks[i]["holding"])

        usercash = db.execute("SELECT cash FROM users WHERE id = %i" % session["user_id"])
        usercash = usercash[0]["cash"]
        totalcash += usercash

        # db.execute("SELECT cash FROM users WHERE id = %i" % session["user_id"])

        return render_template("/index.html", stocks=stocks, totalcash=totalcash, usercash=usercash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # gonna have to create a buy.html template

    if request.method == "POST":

        stock = lookup(request.form.get("symbol"))
        shares = (request.form.get("shares"))

        try:
            float(shares)
        except ValueError:
            return apology("must provide a valid number of stock", 400)

        shares = float(shares)

        # we need to validate a proper STOCK symbol and a non negative integer of shares

        if stock == "":
            return apology("must provide a stock symbol", 400)

        if shares == "":
            return apology("must provide a number of shares", 400)

        if shares.is_integer() != True:
            return apology("must provide valid amount of shares", 400)

        if shares < 1:
            return apology("must provide valid amount of shares", 400)

        if stock is None:
            return apology("the symbol you provided is not a valid stock", 400)

        totalCost = stock["price"] * int(shares)

        # check if the user can afford the transaction
        userCash = db.execute("SELECT cash FROM users WHERE id = %s" % (session["user_id"]))

        if (int(userCash[0]["cash"]) - totalCost) < 0:
            return apology("you dont have enough cash to carry out this transaction", 421)

        else:
            # substract the amount from users cash
            aftermath = (int(userCash[0]["cash"]) - totalCost)
            db.execute("UPDATE users SET cash=%i WHERE id=%i" % (aftermath, session["user_id"]))

            # working from here on up

            if db.execute("SELECT shares FROM portfolio WHERE symbol = '%s' AND user_id = %i" % ((request.form.get("symbol")), session["user_id"])) == []:
                db.execute("INSERT INTO portfolio (user_id , symbol, shares) VALUES(?, ?, ?)",
                           session["user_id"],  request.form.get("symbol"), int(shares))
            # check if the user already owns at least own of this stock
            else:
                db.execute("UPDATE portfolio SET shares = shares + %i WHERE symbol = '%s' AND user_id = %i" %
                           (int(shares), request.form.get("symbol"), session["user_id"]))
            # else insert a new row into the sql database for this stock

            # At this point we are only missing a table to keep a history
            # and later when we implement the history function we will add the other table
            type = "Buy"
            db.execute("INSERT INTO history (user_id, type, symbol, shares, date) VALUES (?,?,?,?,?)",
                       session["user_id"], type, request.form.get("symbol"), int(shares), timeoftransaction)

            return redirect("/")

            # for some reason buy is not processing correctly and accepts negative and non whole positive integers

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    if request.method == "POST":
        return redirect("/")

    else:
        history = db.execute("SELECT * FROM history")

        return render_template("history.html", history=history)


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
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        stock = request.form.get("symbol")

        if stock == "":
            return apology("please input a stock symbol", 400)

        price = lookup(request.form.get("symbol"))

        if price is None:
            return apology("invalid stock symbol", 400)

        else:
            return render_template("quoted.html", stock=stock, price=price)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    name = request.form.get("username")
    usernames = db.execute("SELECT username FROM users WHERE username = '%s'" % name)

    if usernames != []:
        return apology("that user name is already in use", 400)

    if request.form.get("username") == "":
        return apology("must provide username", 400)

    elif request.form.get("username") in usernames:
        return apology("username already in use", 400)

    if request.form.get("password") == "":
        return apology("must provide password", 400)

    if request.form.get("password") != request.form.get("confirmation"):
        return apology("both passwords must be the same", 400)

    if request.method == "POST":
        db.execute("INSERT INTO users (username , hash) VALUES(?, ?)", request.form.get
                   ("username"),  generate_password_hash(request.form.get("password")))
        return render_template("login.html")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # TODO: if user doesnt select a stock or doesnt own any shares of the stock

        if symbol == None:
            return apology("please select a stock", 372)

        if db.execute("SELECT symbol FROM portfolio WHERE user_id = %i AND symbol = '%s'" % (session["user_id"], symbol)) == []:
            return apology("you don't own any of these stock", 368)

        # TODO: require he inputs a valid number of shares (less than he owns and postive int)
        if int(shares) < (1):
            return apology("please input a valid number of shares", 369)

        temp = db.execute("SELECT shares FROM portfolio WHERE user_id = %i AND symbol = '%s'" % (session["user_id"], symbol))
        if int(shares) > temp[0]["shares"]:
            return apology("you are trying to sell more shares than you currently own", 400)

        # TODO: when the user sell we use take the stocks current value and add it to cash
        price = lookup(symbol)
        moneygain = int(shares) * price["price"]

        # remove the money from users cash
        db.execute("UPDATE users SET cash= cash + %i WHERE id=%i" % (moneygain, session["user_id"]))

        # remove the share from portfolio
        db.execute("UPDATE portfolio SET shares = shares - %i WHERE user_id=%i AND symbol = '%s'" %
                   (int(shares), session["user_id"], symbol))

        # add transaction to history

        type = "Sell"

        db.execute("INSERT INTO history (user_id, type, symbol, shares, date) VALUES (?,?,?,?,?)",
                   session["user_id"], type, symbol, int(shares), timeoftransaction)
        return redirect("/")
    else:

        stocks = db.execute("SELECT symbol FROM portfolio WHERE user_id = %i" % session["user_id"])
        # select menu displays all the stock the user has

        return render_template("sell.html", stocks=stocks)

