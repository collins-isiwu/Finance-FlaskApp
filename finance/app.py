import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, checktime

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
    # Query database for the users info stored in table shares
    rows = db.execute("SELECT symbol, name, numshares, price, total FROM shares WHERE id = ? GROUP BY symbol ORDER BY name", session["user_id"])
    print("rows", rows)
    # Query database for the available cash
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = cash[0]["cash"]
    print("cash = ", cash)

    if rows == []:
        grand_total = cash
        print("grand_total1 = ", grand_total)
    else:
        # Query database for the sum of the total
        grand_total = db.execute("SELECT SUM(total) FROM shares WHERE id = ?", session["user_id"])
        print("grand_total2 = ", grand_total)
        grand_total = grand_total[0]["SUM(total)"]
        grand_total = (grand_total + cash)

    return render_template("index.html", rows=rows, cash=cash, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        numshares = request.form.get("shares")

        # Ensure symbol was submitted
        if not symbol:
            return apology("You must input the stock symbol to buy", 400)

        # Ensure number of shares was submitted
        if not numshares:
            return apology("You must enter the number of stock to buy", 400)

        # Security checks
        try:
            # convert numshares to string to be used by isnumeric
            z = str(numshares)

            # check if numshares is non-numeric
            if z.isnumeric() != True:
                return apology("it must be a whole number", 400)

            # convert numshares back to int to be used to check if it is a fraction
            numshares = int(numshares)

            # Check if the num of shares is a fraction
            x = numshares/3
            x = print(x - int(x) == 0)

            # True if x is a whole number, False if it has decimals.
            if x == False:
                return apology("the number of shares to buy must be a whole number", 400)
        except ValueError:
            return apology("wrong", 400)

        # call lookup function
        result = lookup(symbol)

        # validate the stock symbol
        if result == None:
            return apology("the stock symbol doesn't exist", 400)

        # access the value of dict result
        result_name = result['name']
        result_symbol = result['symbol']
        result_price = result['price']

        # convert int to float
        numshares = float(numshares)

        # what it will cost me to buy what quantity of shares of a stock at what price
        total_cost = (numshares * result_price)

        # Query database for cash
        available_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        available_cash = available_cash[0]["cash"]


        """Ensure wether a stock has been bought before or not"""
        # Query database to ensure the company's stock hasn't ever been bought before by a particular user
        rows = db.execute("SELECT name FROM shares WHERE id = ?", session["user_id"])

        # Ensure user has enough cash to afford the stock
        if total_cost <= available_cash:

            # if the user hasn't bought such stock before
            if result_name != rows:

                # run sql statement on database to reflect purchased stock
                db.execute("INSERT INTO shares (id, symbol, name, numshares, price, total) VALUES(?, ?, ?, ?, ?, ?)",
                           session["user_id"], result_symbol, result_name, numshares, result_price, total_cost)

                # Call the checktime() function to get the current time of transaction and update the column time
                check = checktime()
                time_checked = db.execute("UPDATE shares SET time = ? WHERE id = ? AND symbol = ?", check, session["user_id"], result_symbol)

            #if stock exists
            else:
                db.execute("UPDATE shares SET numshares = numshares + ? AND price = ? AND total = total + ? WHERE id = ? AND name = ?",
                           numshares, result_price, total_cost, session["user_id"], result_name)

                # Call the checktime() function to get the current time of transaction and update the column time
                check = checktime()
                time_checked = db.execute("UPDATE shares SET time = ? WHERE id = ? AND symbol = ?", check, session["user_id"], result_symbol)

            # Update available cash
            db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", total_cost, session["user_id"])

            # Redirect user to home page
            return redirect("/")

        # if user can't afford stock, return apology
        else:
            return apology("You can't to buy that amount of shares", 400)

    # returns buy.html if the page is requested via GET mthod
    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT symbol, numshares, price, time FROM shares WHERE id = ? ORDER BY time", session["user_id"])
    return render_template("history.html", rows=rows)


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

        # Obtain users' input and save it in text variable
        text = request.form.get("symbol")

        if not text:
            return apology("must provide symbol", 400)

        # lookup returns the result of the lookup fxn and assigns it to variable results
        result = lookup(text)

        # Handle invalid stock symbol
        if result is None:
            return apology("enter a correct stock symbol", 400)

        # save the result of the look function to the following varables
        result_name = (result.get('name'))
        result_price = (result.get('price'))
        result_symbol = (result.get('symbol'))
        result_price = usd(result_price)

        return render_template("quoted.html", result_name=result_name, result_symbol=result_symbol, result_price=result_price)
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user if the request method is POST"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)

        # confirm password
        elif not confirmation:
            return apology("must confirm password", 400)

        # Ensure that password match
        if password != confirmation:
            return apology("passwords doesn't match")

        """Ensure the username doesn't exist in the database"""
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username doesn't exists and password is correct
        if len(rows) != 0:
            return apology("username already exists", 400)

        # hash the user's password
        hash_password = generate_password_hash(password)

        # Store username and password in SQL
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash_password)
        return redirect("/login")

        """print register.html if request method is GET"""
    elif request.method == "GET":
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        # ask flask for the users' input
        symbol_input = request.form.get("symbol")
        share_input = request.form.get("shares")

        # check if user inputed a symbol
        if not symbol_input:
            return apology("pls select a stock", 400)

        # check if user inputed a share amt to sell
        if not share_input:
            return apology("pls enter the amount of shares to sell", 400)

        # Security checks
        try:
            # convert share_input to string to be used by isnumeric
            z = str(share_input)

            # check if share_input is non-numeric
            if z.isnumeric() != True:
                return apology("it must be a whole number", 400)

            # convert share_input back to int to be used to check if it is a fraction
            share_input = int(share_input)

            # Check if share_input is a fraction
            x = share_input/3
            x = print(x - int(x) == 0)

            # True if x is a whole number, False if it has decimals.
            if x == False:
                return apology("the number of shares to buy must be a whole number", 400)
        except ValueError:
            return apology("wrong", 400)


        # call lookup function
        result = lookup(symbol_input)
        # validate the stock symbol
        if result == None:
            return apology("the stock symbol doesn't exist", 400)


        # Query database for data
        row = db.execute("SELECT symbol FROM shares WHERE id = ?", session["user_id"])
        # validate the stock symbol
        if row == None:
            return apology("the stock you're trying to sell doesn't exist in your portfolio", 400)


        # Query database for data
        row = db.execute("SELECT numshares, price FROM shares WHERE id = ? AND symbol = ?", session["user_id"], symbol_input)
        row_shares = row[0]["numshares"]
        row_shares = int(row_shares)
        row_price = row[0]["price"]

        # check if the user is seeking to sell the amount of shares they have
        if row_shares < share_input:
            return apology("you don't have that amount of shares in your portfolio, enter the correct amount to sell", 400)

        # check if the user is selling all the shares they have, if yes, delete their entire record about that stock
        if row_shares == share_input:
            db.execute("DELETE FROM shares WHERE id = ? AND symbol = ?", session["user_id"], symbol_input)

            # Call the checktime() function to get the current time of transaction and update the column time
            check = checktime()
            time_checked = db.execute("UPDATE shares SET time = ? WHERE id = ? AND symbol = ?", check, session["user_id"], symbol_input)

        # if user still pose some shares after selling, update his/her record about the stock
        else:
            cost_of_sell = (row_price * share_input)
            db.execute("UPDATE users SET cash = cash + ?", cost_of_sell)
            db.execute("UPDATE shares SET numshares = numshares - ?, total = total - ?", share_input, cost_of_sell)

            # Call the checktime() function to get the current time of transaction and update the column time
            check = checktime()
            time_checked = db.execute("UPDATE shares SET time = ? WHERE id = ? AND symbol = ?", check, session["user_id"], symbol_input)


        # Redirect user to home page
        return redirect("/")

    else:
        rows = db.execute("SELECT symbol FROM shares WHERE id = ?", session["user_id"])
        print("row = ", rows)
        return render_template("sell.html", rows=rows)

if __name__ == "__main__":
    app.run(debug=True)