from piazza_api import Piazza
from DBManager import *
from Constants import *
import string

class PiazzaQuestions(object):
    """Wrapper for Piazza API. Use to login user and retreive the most
    recent quiz questions posts"""

    def __init__(self):
        self.p = Piazza()
        self.class_id = None
        self.dbManager = DBManager(DB_NAME)

    def login_user(self):
        """Log in user with credentials stored in database

        Returns:
            -1 if login fails
        """
        creds = self.dbManager.get_credentials()
        try:
            self.p.user_login(creds[1], creds[2])
            self.class_id = self.p.network(creds[3])
        except Exception as e:
            return -1

    def sanitize_input(self, string_value):
        """Removes non-printable characters from string_value. This
        is a necessary step before adding a question to the database.

        Keyword arguments:
            string_value -- input read from piazza

        Returns:
            string_value with non printable characters removed
        """
        return "".join(s for s in string_value if s in string.printable)

    def parse_question(self, post):
        """Parse a question into answer, question, and answer choicesself.
        question must be of form #answer# question[?.] (choice1) text (choice_n) text
        ex) #A# Should arrays start at 1? (A) NO (B) still no (C) also no

        Keyword arguments:
            post -- the question from piazza

        Returns:
            -1 if question could not be parsed. If succesfully paresed, a tuple
            is returned: (answer, question, choices)
        """
        # parse answer
        start = post.find("#")
        end = post[start + 1:].find("#")
        if (start == -1 or end == -1):
            return -1
        start += 1
        end = end + start
        answer = post[start:end]

        # parse question
        start = end + 1
        end = post[start:].find("?")
        if (end == -1):
            end = post[start:].find(".")
            if (end == -1):
                return -1
        end = end + start + 1
        question = post[start:end]

        # parse choices
        choices = post[end + 1:]
        # if punctuation is at end there will be no choices,
        # this check is for a min of (A)
        if (len(choices.replace(" ", "")) < 3):
            return -1

        return (answer, question, choices)

    def is_quiz_post(self, post_title):
        """
        Keyword arguments:
            post_title -- the piazza post's title

        Returns:
            True if this is a quiz post, false if it is any other kind
            of post
        """
        return (post_title.find("week") != -1
            and post_title.find("submit") != -1
            and post_title.find("quiz") != -1)


    def find_all_quiz_questions(self):
        """Finds all posts on piazza that contain submitted quiz
        questions and writes them to the database. A post is recognized
        as a submitted questions post if the key words 'week', 'submit',
        and 'quiz' are found in the post's title

        Returns:
            -1 if fails to get all posts
        """
        try:
            all_posts = self.class_id.iter_all_posts()
        except Exception as e:
            print("User not logged in")
            return -1
        for post in all_posts:
            date = post['history'][0]['created']
            title = (post['history'][0]['subject']).lower()
            if (self.is_quiz_post(title)):
                print("Found: ", date[:date.find('T')], title)
                post_nr = post['nr']
                # add quiz
                result = self.dbManager.store_quiz(post_nr, date, title)
                if (result == -1):
                    print("Failed to add quiz")
                    continue
                elif (result == 0):
                    print("Quizzes are up to date")
                    break
                # add questions
                all_questions = []
                content = post['history'][0]['content'][3:]
                while(True):
                    i = content.find("<br")
                    if (i == -1):
                        break
                    question = content[:i]
                    content = content[i:]
                    content = content[content.find(">") + 1:]
                    question_values = self.parse_question(question)
                    if (question_values != -1):
                        all_questions.append(
                        (self.sanitize_input(question_values[0]),
                        self.sanitize_input(question_values[1]),
                        self.sanitize_input(question_values[2]),
                        post_nr, 0))
                self.dbManager.store_questions(all_questions)

    def first_time_login(self, username, password, class_id):
        """Attempt to login user for the first time and then
        set up their course. If succesful, will store user credentials
        and then search piazza for all quiz questions.

        Keyword arguments:
            username -- user's piazza email
            password -- user's piazza password
            class_id -- piazza course id for class

        Returns:
            0 if login fails, -1 if class id is incorrect
        """
        try:
            self.p.user_login(username, password)
        except Exception as e:
            return 0

        try:
            self.class_id = self.p.network(class_id)
            self.class_id.get_post(1)
        except Exception as e:
            return -1;

        # login and course id succesful, add credentials to database
        if (self.dbManager.store_credentials(username, password, class_id) != -1):
            print("Succesfully logged in User!")
        else:
            print("Failed to add new user")

        print("Searching Piazza for all quiz questions, this may take a few minutes...")
        if (self.find_all_quiz_questions() == -1):
            print("Fialed to add all quiz questions")
