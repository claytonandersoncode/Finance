import os
import datetime

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    if request.method == "GET":
        """Show portfolio of stocks"""
        stocks = db.execute("SELECT symbol, name, SUM(shares) FROM transactions WHERE id = :id GROUP BY symbol HAVING SUM(shares) > 0", id=session["user_id"])
        sharestotal = 0
        for stock in stocks:
            stock["price"] = lookup(stock["symbol"])["price"]
            quantity = stock["SUM(shares)"]
            stock["value"] = stock["price"] * quantity
            sharestotal += stock["value"]

        #Select cash for user 
        cashtotal = db.execute("SELECT cash FROM users WHERE id = :id",
                          id=session["user_id"])[0]["cash"]

        #Display total for user 
        total = sharestotal + cashtotal

        #Redirect to index
        return render_template("index.html", stocks=stocks, cashtotal=cashtotal, total=total)

    return apology("Page not found, Please try again", 404)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else: 
        """Buy shares of stock"""
        userid = session["user_id"]

        #Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide a symbol", 403)

        #Ensure shares was submitted
        elif not request.form.get("shares"):
            return apology("must enter a share", 403)

        #Enusre shares is a positive integer
        elif int(request.form.get("shares")) <= 0:
            return apology("must enter a positive integer", 403) 

        #Ensure symbol is valid from lookup
        lookedup = lookup(request.form.get("symbol"))
        if not lookedup:
            return apology("must provide a valid symbol", 403)

        #Calculate cost of purchase
        cost = lookedup["price"] * int(request.form.get("shares"))

        # Qeury database for username
        username = db.execute("SELECT username FROM users WHERE id = :id", id=userid)[0]["username"]

        # Query database for users available cash 
        cash = db.execute("SELECT cash FROM users WHERE id = :id",
                          id=userid)[0]["cash"]
                          
        #Ensure user has enough money
        if cash < cost:
            return apology("insufficient funds for transaction", 403)

        #buy logic
        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=(cash-cost), id=userid)
        db.execute("INSERT INTO transactions (id, username, symbol, name, shares, price, value, type, time) VALUES (:id, :username, :symbol, :name, :shares, :price, :value, :type, :time)", id=userid, username=username, symbol=request.form.get("symbol"),name=lookedup["name"], shares=request.form.get("shares"), price=lookedup["price"], value=cost, type="buy", time=datetime.datetime.now())

        #redirect to home
        return redirect("/")
    
    return apology("Page not found, Please try again", 404)

@app.route("/history")
@login_required
def history():
    if request.method == "GET":
        """Show history of transactions"""
        transactions = db.execute("SELECT * FROM transactions WHERE id = :id", id=session["user_id"])

        #Render history page
        return render_template("history.html", transactions=transactions)

    return apology("Page not found, Please try again", 404)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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
    if request.method == "GET":
        return render_template("quote.html")
    else:
        """Get stock quote."""
        #Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        #Ensure valid symbol length
        elif len(request.form.get("symbol")) > 5:
            return apology("must provide a valid symbol", 403)
        
        #Perform lookup
        quote = lookup(request.form.get("symbol"))

        #Redirect to Quoted
        return render_template("quoted.html", quote=quote)

    return apology("Page not found, Please try again", 404)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        """Register user"""
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 403) 

        # Ensure password and confirmation match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("the passwords did not match, try again", 403) 

        # Query database for username and check it does not exist 
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username does not exist 
        if len(rows) == 1:
            return apology("username already exists", 403)
        
        # Add user and password into database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"), hash=generate_password_hash(request.form.get("password")))
        
        # Redirect to home page
        return redirect("/")

    return apology("Page not found, Please try again", 404)
   

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """ Sell Shares of Stock """
    if request.method == "GET":
        # Display list of stocks to sell
        stocks = db.execute("SELECT symbol, SUM(shares) FROM transactions WHERE id = :id GROUP BY symbol HAVING SUM(shares) > 0", 
                        id=session["user_id"])
        return render_template("sell.html", stocks=stocks)
    else: 
        #Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide a symbol", 403)

        #Ensure shares was submitted
        elif not request.form.get("shares"):
            return apology("must enter a share", 403)

        #Enusre shares is a positive integer
        elif int(request.form.get("shares")) <= 0:
            return apology("must enter a positive integer", 403) 

        #Ensure symbol is valid from lookup
        lookedup = lookup(request.form.get("symbol"))
        if not lookedup:
            return apology("must provide a valid symbol", 403)

        #Calculate revenue of sale
        revenue = lookedup["price"] * int(request.form.get("shares"))

        # Qeury database for username
        username = db.execute("SELECT username FROM users WHERE id = :id",
                        id=session["user_id"])[0]["username"]

        # Query database for users available cash 
        cash = db.execute("SELECT cash FROM users WHERE id = :id",
                        id=session["user_id"])[0]["cash"]
                          
        #Ensure user has enough shares
        owned = (db.execute("SELECT sum(shares) FROM transactions WHERE id = :id AND symbol = :symbol",
                        id=session["user_id"], symbol=request.form.get("symbol")))[0]["sum(shares)"]
        if owned <= 0 :
            return apology("insufficient shares for transaction", 403)

        #sell logic
        soldshares = (int(request.form.get("shares")) * -1)
        db.execute("INSERT INTO transactions (id, username, symbol, name, shares, price, value, type, time) VALUES (:id, :username, :symbol, :name, :shares, :price, :value, :type, :time)", 
                        id=session["user_id"], username=username, symbol=request.form.get("symbol"),name=lookedup["name"], shares=soldshares, price=lookedup["price"], value=revenue, type="sell", time=datetime.datetime.now())
        db.execute("UPDATE users SET cash = :cash WHERE id = :id",
                        cash=(cash+revenue), id=session["user_id"])

        #redirect to home
        return redirect("/")

    return apology("Page not found, Please try again", 404)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
