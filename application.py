# werkzeug needs to be downgraded to 0.16 -> pip install werkzeug=0.16

import os
import requests
import json

from flask import Flask, session, render_template, request, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# SQLalchemy
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

#Intro page
@app.route("/", methods=["GET", "POST"])
def index():
    if "user_id" in session:
        return render_template("logged.html")

    else:
        return render_template("index.html")

#To register:
@app.route("/register", methods=["POST"])
def register():
    # Getting form information
    user_name = request.form.get("user_name")
    user_password = request.form.get("user_password")

    if db.execute("SELECT * FROM registered WHERE user_name=:user_name", {"user_name": user_name}).rowcount != 0:
        return render_template('error.html', message="This username is already taken. Please try a different one")
    # need to add validation whether username or password wasnt null

    db.execute("INSERT INTO registered (user_name, user_password) VALUES (:user_name, :user_password)",
               {"user_name": user_name, "user_password": user_password})
    db.commit()
    print('ok')
    return render_template("success.html", user_name=user_name)

# Login:
@app.route("/login", methods=["POST"])
def login():
    user_name = request.form.get("user_name")
    user_password = request.form.get("user_password")

    if db.execute(
            "SELECT * FROM registered WHERE user_name = :user_name AND user_password=:user_password", {"user_name": user_name, "user_password": user_password}).rowcount == 0:
        return render_template("error.html", message="Incorrect username or password. :(")
    else:
        user_id = db.execute("SELECT user_id FROM registered WHERE user_name = :user_name AND user_password=:user_password", {
            "user_name": user_name, "user_password": user_password}).fetchone()[0]
        session["user_id"] = user_id
        print(session["user_id"])
        return render_template("logged.html")

#Logout:
@app.route("/seeyoulater", methods=["POST"])
def logout():
    if "user_id" in session:
        session.pop("user_id", None)
    return  render_template("seeyoulater.html")

#Searching results
@app.route("/search", methods=["POST"])
def search():
    searched = request.form.get("searched_book")

    searched_book = "%"+searched+"%"

    books = db.execute("SELECT * FROM books WHERE isbn LIKE :isbn OR UPPER(author) LIKE UPPER(:author) OR UPPER(title) LIKE UPPER(:title)", {"isbn": searched_book, "author": searched_book, "title": searched_book}).fetchall()

    return render_template("results.html", books = books)

#Book's details
@app.route("/details/<book_isbn>")
def details(book_isbn):
    if not "user_id" in session:
        return render_template('error.html', message="You have to login first to access this page.")

    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": book_isbn}).fetchone()
    review = db.execute("SELECT * FROM reviews WHERE isbn =:isbn AND user_id=:user_id", {"isbn": book_isbn, "user_id":session["user_id"] }).fetchone()
    if review is None:
        is_review = False
        book_rate = None
        book_comment = None
    else:
        is_review = True
        book_rate = db.execute("SELECT rate FROM reviews WHERE isbn =:isbn AND user_id=:user_id", {"isbn": book_isbn, "user_id":session["user_id"] }).fetchone()[0]
        book_comment = db.execute("SELECT user_comment FROM reviews WHERE isbn =:isbn AND user_id=:user_id", {"isbn": book_isbn, "user_id":session["user_id"] }).fetchone()[0]
        if len(book_comment) == 0:
            book_comment = "----"
    rates=[1,1.5,2,2.5,3,3.5,4,4.5,5]

    #### Goodreads:
    KEY = open('key.txt', 'r').read()
    res = requests.get("https://www.goodreads.com/book/review_counts.json",
                       params={"key": f"{KEY}", "isbns": book_isbn})
    goodreads = res.json()
    goodreads_people = goodreads['books'][0]['work_ratings_count']
    goodreads_rate= goodreads['books'][0]['average_rating']
    return render_template("details.html", book = book, is_review = is_review, rates = rates, book_rate = book_rate, book_comment =book_comment, goodreads_rate=goodreads_rate, goodreads_people=goodreads_people)

#Submitting new review:
@app.route("/details/<book_isbn>/rated", methods=["POST"])
def rating(book_isbn):
    book_comment = request.form.get("review-comment")
    book_rate = request.form.get("rate")
    #double check if rate not empty:
    if len(book_rate) == 0:
        return render_template('error.html', message="You have to rate the book from 1 to 5.")
    if db.execute("SELECT * FROM reviews WHERE isbn =:isbn AND user_id=:user_id", {"isbn": book_isbn, "user_id":session["user_id"] }).rowcount != 0:
        return render_template('error.html', message="You have already rated this book!")
    db.execute("INSERT INTO reviews (user_id, isbn, rate, user_comment) VALUES (:user_id, :isbn, :rate, :user_comment)", {"user_id":session["user_id"], "isbn":book_isbn, "rate": book_rate, "user_comment": book_comment})
    db.commit()
    return details(book_isbn)
