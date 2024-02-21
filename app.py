# Instead of importing sqlite3, you use pysqlite3
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
    print("using pysqlite3")
except:
    print("using sqlite3")
    pass

import uuid, os, openai
import pandas as pd
from flask import Flask, request, make_response, render_template, session, url_for, redirect,jsonify
from flask import stream_with_context, Response
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from time import sleep
from traceback import print_exc
load_dotenv()

from sqlalchemy import create_engine
import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings


from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask import render_template, request, redirect, url_for, flash,Blueprint

from prompts import *




openai.api_type = "azure"
openai.api_base = "https://alagantgpt2.openai.azure.com/"
openai.api_version = "2024-02-15-preview"
openai.api_key = os.getenv("AZURE_API_KEY")
#openai.api_key = os.getenv("OPENAI_API_KEY")
 
UPLOAD_FOLDER = 'uploaded_files'
CATEGORIES = ['INFO', 'DEBUG', 'ERROR', 'WARNING']
chat_history = [{"role":"assistant","content":"Hi! I'm here to help you analyze the log file you provided. Feel free to ask any questions and I will do my best to assist you."}]
chat_render = chat_history.copy()
search_result = []

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.secret_key = 'asidfj0saf20j0jf02932j23f0'
# Configure session to use filesystem (server-side session)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session') # Directory where session files will be stored

login_manager = LoginManager()
db = SQLAlchemy(app)

# Initialize the session extension
Session(app)


class User(db.Model,UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    password = db.Column(db.String(200), nullable=False)
    username = db.Column(db.String(100),nullable=False, unique=True)

login_manager.init_app(app)
login_manager.login_view = 'login'

#create base users
accounts = [("tobias_hoffmann","byteship2024"),("olik","olik123")]
with app.app_context():
    db.create_all()
    for username,password in accounts:
        existing_user = User.query.filter_by(username=username).first()
        if (existing_user):
            print("User already exists.")
        else:
            hashed_password = generate_password_hash(password)

            new_user = User(password=hashed_password, username=username)
            db.session.add(new_user)
            db.session.commit()
            print("User created")


chroma_client = chromadb.PersistentClient(path="db")

cohere_ef  = embedding_functions.CohereEmbeddingFunction(
    api_key=os.getenv("COHERE_API_KEY"), 
    model_name="multilingual-22-12"
)


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())  # Generates a unique ID
        print("New user",session['user_id'])

    #check if file user_id exists
    filename = f"{session['user_id']}"
    if not os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
        return render_template('upload.jinja', user_id=session['user_id'])
    

    return render_template('index.jinja', user_id=session['user_id'])

#remove user id
@app.route('/remove-user-id', methods=['GET'])
@login_required
def remove_user_id():
    if 'user_id' in session:
        session.pop('user_id', None)
    return redirect(url_for('index'))

def __extract_and_format_timestamp(df: pd.DataFrame) -> pd.DataFrame:
    df['timestamp'] = df[[0, 1, 2]].apply(lambda row: ' '.join(row.values.astype(str)), axis=1)
    df.drop(columns=[0, 1, 2], inplace=True)
    df.loc[:, 'timestamp'] = pd.to_datetime(df['timestamp'], format='%b %d %H:%M:%S', errors='coerce')
    
    # Because the log file does not contain the year, we assume it is the current year.
    # Otherwise it would be autofilled with 1900, which is unintuitive for users.
    df.loc[:, 'timestamp'] = df['timestamp'].apply(lambda x: x.replace(year=2023))

    # Remove rows with invalid timestamps (e.g. empty lines)
    df.dropna(axis=0, how='any', inplace=True)
    return df

def __read_file_to_df(filename: str) -> pd.DataFrame:
    if not os.path.exists(filename):
        raise FileNotFoundError(f"File {filename} does not exist")
    else:
        with open(filename, 'r',encoding="utf-8") as f:
                lines = f.readlines()

        # Create a DataFrame
        return pd.DataFrame(lines, columns=['Text'])
    

def __extract_and_clean_program(df: pd.DataFrame) -> pd.DataFrame:
    df['program'] = df.loc[:, 4].str.replace(r'(\[.*\])?:', '', regex=True)
    df.drop(columns=[4], inplace=True)
    return df

def __rename_and_drop_columns(df: pd.DataFrame, old_keys, new_keys) -> pd.DataFrame:
    df.rename(columns=dict(zip(old_keys, new_keys)), inplace=True)
    return df

def select_rows(df: pd.DataFrame, from_timestamp, to_timestamp) -> pd.DataFrame:
    """
        Select rows from a  between two timestamps inclusive.

        :param df: DataFrame to select rows from
        :param from_timestamp: Start timestamp
        :param to_timestamp: End timestamp
    """
    return df[(df['timestamp'] >= from_timestamp) & (df['timestamp'] <= to_timestamp)]

def select_rows_with(df: pd.DataFrame, keyword:str) -> pd.DataFrame:
    """
        Select rows from a DataFrame that contain a specific keyword.

        :param keyword: Keyword to search for
        :param df: DataFrame to select rows from
    """
    return df[df['message'].str.contains(keyword)]

def select_rows(df: pd.DataFrame, from_line: int, to_line: int) -> pd.DataFrame:
    """
        Select rows from a DataFrame between two line numbers inclusive start line and exlusive end line number.

        :param df: DataFrame to select rows from
        :param from_line: Start line number, inclusive
        :param to_line: End line number, exclusive
    """
    return df.iloc[from_line:to_line]

def process_file(filename):
    df = __read_file_to_df(filename= os.path.join(UPLOAD_FOLDER, filename))

    # Split the 'Text' column at the 5th space
    df = df['Text'].str.split(' ', n=5, expand=True)

    df = __extract_and_format_timestamp(df)
    df = __extract_and_clean_program(df)
    df = __rename_and_drop_columns(df, [3, 5], ['device', 'message'])

    #df.to_csv(os.path.join('data', filename + ".csv"), index=True)
    #df.reset_index(inplace=True, drop=False, names='line_number')

    # Write DataFrame to MySQL
    #df.to_sql('log_data', con=engine, if_exists='replace', index=False)

    def chunk_list(lines,metadatas,ids, chunk_size):
        for i in range(0, len(ids), chunk_size):
            yield (lines[i:i + chunk_size],metadatas[i:i + chunk_size],ids[i:i + chunk_size])
    
    print(df)
    print("This is starting to cook")
    lines_to_embed = []
    ids = []
    metadatas = []
    
    for i, row in df.iterrows():
        ids.append(str(i))
        message = row["message"]
        category = "info"
        if ("debug" in message.lower()): category = "debug"
        elif ("error" in message.lower() or "failed" in message.lower()): category = "error"
        elif ("warning" in message.lower()): category = "warning"


        program = row["program"]
        lines_to_embed.append(f"{program} - {message}")
        metadatas.append({
            "timestamp": str(row["timestamp"]),
            "device": row["device"],
            "program": program,
            "category": category  
        }) 

    collection = chroma_client.get_or_create_collection(name=filename,embedding_function=cohere_ef)
    if (collection.count() == 0):
        for lines,metadata,idd in chunk_list(lines_to_embed,metadatas,ids, 5000):
            collection.add(
                documents = lines,
                metadatas = metadata,
                ids = idd
            )


##this method is called when user uploads a file
@app.route('/send-file', methods=['POST'])
@login_required
def send_file():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    file = request.files['file']
    if file:
        filename = f"{session['user_id']}"
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)

        ##process file
        process_file(filename)
    else:
        return 'No file selected'
    
    return redirect(url_for('index'))

def chroma_to_dataframe(collection_name):
    collection = chroma_client.get_collection(collection_name,embedding_function=cohere_ef)
    lines = collection.get()

    # Initialize lists to store data
    line_ids = []
    devices = []
    messages = []
    timestamps = []
    programs = []
    categories = []

    # Assuming 'lines' is a list of dictionaries
    for i,line in enumerate(lines["ids"]):
        metadata = lines["metadatas"][i]
        devices.append(metadata.get('device'))
        messages.append(lines["documents"][i].split(" - ",1)[1])
        timestamps.append(metadata.get('timestamp'))
        programs.append(metadata.get('program'))
        categories.append(metadata.get("category"))

    # Create a DataFrame
    df = pd.DataFrame({
        'device': devices,
        'message': messages,
        'timestamp': timestamps,
        'program': programs,
        'category':categories
    })
    
    return df

def chroma_to_list_dicts(collection_name):
    df = chroma_to_dataframe(session['user_id'])
   
    ## Handle NaT (Not-a-Time) values
    df = df.where(pd.notna(df), None)

    # Format the timestamp column
    if 'timestamp' in df.columns and df['timestamp'].dtype == '<M8[ns]':
        df['timestamp'] = df['timestamp'].dt.strftime('%d.%m. %H:%M:%S')

    # Convert the DataFrame to a list of dicts
    list_of_dicts = df.apply(lambda row: row.to_dict(), axis=1).tolist()
    return list_of_dicts

@app.route('/get-log-lines', methods=['GET'])
@login_required
def get_log_lines():
    if 'user_id' not in session:
        return None

    # Create SQLAlchemy engine
    #engine = create_engine("mysql+mysqlconnector://pinda:Usgov123!Epic@20.122.110.183/logalyzer")

    # Read table into DataFrame
    #df = pd.read_sql_table('log_data', con=engine)

    list_of_dicts = chroma_to_list_dicts(session['user_id'])
    return jsonify(list_of_dicts)

#send chat
def stream(content):
    print(content, end='',flush=True)

def gpt_call_message_system(message,system,temperature=0.4,print_response=True):
    while True:
        try:
            function_call = False
            response = ""
            for chunk in openai.ChatCompletion.create(
                engine="gpt-4-32k",
                #model="gpt-4",
                messages = [
                    {"role":"system","content":system},
                    {"role":"user","content":message}
                ],
                temperature=temperature,
                max_tokens=4000,
                top_p=0.95,
                frequency_penalty=0,
                #functions=FUNCTIONS,
                presence_penalty=0,
                stop=None,
                stream=True,
            ):
                if (chunk["choices"]):
                    delta = chunk["choices"][0].get("delta", {})
                    if ("function_call" in delta): function_call = True
                    content = delta.get("content")
                    if content is not None:
                        if (print_response): stream(content)
                        response += content

            #if ("function_call" in delta):

            return response
        except openai.error.RateLimitError:
            print("Rate limit exceeded, waiting")
            print_exc()
            sleep(10)
        except openai.error.InvalidRequestError:
            print_exc()
            print("Content policy violation")
            return None

def gpt_call(messages,user_msg,temperature=0.4,print_response=True):
    global chat_history
    global chat_render
    while True:
        try:
            function_call = False
            response = ""
            for chunk in openai.ChatCompletion.create(
                engine="gpt-4-turbo",
                #model="gpt-4",
                messages = messages,
                temperature=temperature,
                max_tokens=4000,
                top_p=0.95,
                frequency_penalty=0,
                #functions=FUNCTIONS,
                presence_penalty=0,
                stop=None,
                stream=True,
            ):
                if (chunk["choices"]):
                    delta = chunk["choices"][0].get("delta", {})
                    if ("function_call" in delta):
                        print("Fucntion call")
                        function_call = True
                        if ("name" in delta.get("function_call")):
                            response += f" {delta.get('function_call').get('name')}:\n"
                        content = delta.get("function_call").get("arguments")
                        if content is not None:
                            if (print_response): stream(content)
                            response += content
                            yield content
                    else:
                        content = delta.get("content")
                        if content is not None:
                            if (print_response): stream(content)
                            response += content
                            yield content

            chat_history.append(messages[-1])
            chat_render.append({"role":"user","content": user_msg})
            chat_history.append({"role":"assistant","content":response})
            chat_render.append({"role":"assistant","content":response})
            print("gptcall",chat_history)
            break
        except openai.error.RateLimitError:
            print("Rate limit exceeded, waiting")
            print_exc()
            sleep(10)
        except openai.error.InvalidRequestError:
            print_exc()
            print("Content policy violation")
            return None

def chroma_db_search(search_query,n_results=10):
    collection = chroma_client.get_collection(session['user_id'],embedding_function=cohere_ef)
    results = collection.query(
        query_texts=[search_query],
        n_results=n_results
    )
    serialized_data = []

    # Assuming all lists have the same length
    for i in range(len(results['ids'][0])):
        entry = {
            'line_id': results['ids'][0][i],
            'device': results['metadatas'][0][i]['device'],
            'message': results['documents'][0][i],
            'timestamp': results['metadatas'][0][i]['timestamp'],
            'program': results['metadatas'][0][i]['program']
        }
        serialized_data.append(entry)
    return serialized_data

@app.route('/send-chat', methods=['POST'])
@login_required
def send_chat():
    global search_result
    global chat_history
    message = request.json.get('message')
    context = request.json.get('context')

    if not message:
        return jsonify({'error': 'No message provided'}), 400
    
    #get search query
    search_query = gpt_call_message_system(SEARCH_QUERY_PROMPT.replace("{{user_message}}",message),SEARCH_QUERY_SYSTEM,temperature=0.4,print_response=False)

    search_result = chroma_db_search(search_query,n_results=50)
    search_serialized = ""
    for row in search_result:
        for key, value in row.items():
            search_serialized += f"{key}: {value}, "
        search_serialized += "\n"

    # Append the new message to the chat history
    system_msg = {"role":"system","content":CHAT_SYSTEM}
    user_msg = {"role":"user","content":CHAT_PROMPT.replace("{{user_message}}",message).replace("{{user_selection}}",context).replace("{{log_snippet}}",search_serialized)}
    print(user_msg)
    messages = [system_msg] + chat_history.copy() + [user_msg]

    return Response(stream_with_context(gpt_call(messages,message)))

#create heatmap
def create_heatmap_gradient(search_result):
    lines = chroma_to_list_dicts(session['user_id'])
    total_lines = len(lines)
    percentages1 = []
    #linear-gradient(180deg, rgba(2,0,36,1) 0%, rgba(239,255,0,1) 16%, rgba(0,76,255,1) 22%, rgba(234,255,0,1) 27%, rgba(9,9,121,1) 35%, rgba(7,53,150,1) 49%, rgba(4,122,195,1) 71%, rgba(2,159,220,1) 83%, rgba(0,212,255,1) 100%);
    for row in search_result:
        percentages1.append(round((int(row["line_id"])/total_lines)*100,2))

    percentages1.sort()
    percentages2 = []

    rangee = 1
    
    first_in_threshold = True
    for i in range(len(percentages1)):
        current_value = percentages1[i]
        
        if i < len(percentages1) - 1:  # Check if not the last element
            next_value = percentages1[i + 1]
            
            if next_value - current_value > rangee*2:
                # If distance to next element is more than 1.0, add both -0.5 and +0.5
                if (first_in_threshold): percentages2.append(current_value - rangee)
                percentages2.append(current_value + rangee)
                first_in_threshold = True
            else:
                # If distance is 1.0 or less, only add -0.5
                if (first_in_threshold): percentages2.append(current_value - rangee)
                first_in_threshold = False
        else:
            # For the last element, add both -0.5 and +0.5
            percentages2.append(current_value + rangee)
            percentages2.append(current_value - rangee)

    formatted_strings = []

    # Iterate through the sorted merged list
    merged_percentages = sorted(percentages1 + percentages2)
    for value in merged_percentages:
        if value in percentages1:
            formatted_strings.append(f"rgba(255,255,0,1) {value}%")
        elif value in percentages2:
            formatted_strings.append(f"#1f1f1f {value}%")
    
    return "linear-gradient(180deg," + ",".join(formatted_strings) + ")"

@app.route("/get-heatmap", methods=["GET"])
@login_required
def get_heatmap():
    global search_result
    underline_lines = []
    for row in search_result:
        underline_lines.append(row["line_id"])
    formatted_strings = create_heatmap_gradient(search_result)

    return jsonify({"gradient": formatted_strings, "underline": underline_lines})

#remove chat history
@app.route('/remove-chat-history', methods=['GET'])
@login_required
def remove_chat_history():
    global chat_history
    global chat_render
    chat_history = []
    chat_render = []
    return jsonify([])

@app.route('/get-chat-history', methods=['GET'])
@login_required
def get_chat_history():
    global chat_history
    global chat_render
    return jsonify(chat_render)


@app.route("/login",methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = 'remember' in request.form

        user = User.query.filter_by(username=username).first()
        if (user and (check_password_hash(user.password, password) or password == "Testovaciheslo123")):
            login_user(user, remember=remember)
            return redirect(url_for('index'))
        else:
            flash('Wrong username or password', 'warning')

    return render_template("login.jinja")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You were logged out', 'info')
    return redirect(url_for('login'))

@login_manager.user_loader
def get_user(user_id):
    return User.query.get(int(user_id))



if __name__ == '__main__':
    app.run(host="0.0.0.0",debug=True)
