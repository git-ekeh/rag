from flask import Flask, request, jsonify, render_template, send_from_directory, session
from flask_session import Session
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from openai import OpenAI
import secrets
import chromadb
import logging
import os



logger = logging.getLogger(__name__)
logging.basicConfig(filename='text_processing.log', encoding = 'utf-8', level=logging.DEBUG)


app = Flask(__name__, static_folder='build', static_url_path='/')

# Configure the session
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Connect to ChromaDB on a persistent connection
chroma_client = chromadb.HttpClient(host='localhost', port=8001)

class EmbeddingFunction:
    def __init__(self, model_name):
        self.model = HuggingFaceEmbeddings(model_name=model_name)

    def __call__(self, input):
        return self.model.embed_documents(input)

embedding_function = EmbeddingFunction(model_name="all-MiniLM-L12-v2")

def process_document(text_data, domain_name):
    try:
        logger.debug("Starting process_document function")
        documents = [Document(page_content=text) for text in text_data]
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50)
        all_splits = text_splitter.split_documents(documents)

        # Ensure domain_name is a string
        if isinstance(domain_name, list) and len(domain_name) > 0:
            domain_name = domain_name[0]
        elif not isinstance(domain_name, str):
            domain_name = str(domain_name)

        # Create or get a persistent ChromaDB collection
        collection = chroma_client.get_or_create_collection(name=domain_name, embedding_function=embedding_function)

        # Prepare data for adding to ChromaDB
        docs_content = [split.page_content for split in all_splits]
        doc_ids = [f"{domain_name}_{i}" for i in range(len(all_splits))]
        metadata = [{'domain': domain_name} for _ in all_splits]


        # Add data to the ChromaDB collection
        collection.add(
            documents=docs_content,
            metadatas=metadata,
            ids=doc_ids
        )

        logger.debug("process_document function completed successfully")
        return True
    except Exception as e:
        logger.error("Error in process_document function: %s", e)
        return False


def retrieve_documents(query, domain_name):
    try:

        # Retrieve documents from the ChromaDB collection
        collection = chroma_client.get_collection(name=domain_name, embedding_function=embedding_function)
        results = collection.query(
            query_texts=[str(query)],
            n_results=1,
            include= ["documents"]
        )

        return results
    except Exception as e:
        logger.error("Error in retrieve_documents function: %s", e)
        return None

def generate_response(context, query):
    client = OpenAI()
    try:
        prompt = f"Based on the following context, answer the question in a detailed and conversational manner:\n\nContext: {context}\n\nQuestion: {query}\n\nAnswer:"
        completion = client.chat.completions.create(
            model="gpt-4",
            messages =[
                {"role": "system", "content": prompt}
                ]
        )
        response = completion.choices[0].message if completion.choices[0].message else ''
        return response
    except Exception as e:
        logger.error("Error in generate_response function: %s", e)
        return "I am sorry, I could not generate a response."

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.json
        query = data.get('question')
        domain_name = data.get('domain')

        #logger.debug("Session data in ask endpoint: %s", session.items())
        logger.debug("Received request data: %s", data)
        logger.debug("Received domain: %s", domain_name)
        logger.debug("Received question: %s", query)

        # Validate domain_name
        if not domain_name:
            logger.error("Domain name is missing in request")
            return jsonify({'error': 'Domain name is missing. Document must not exist'}), 400

        # Retrieve documents from ChromaDB collection
        results = retrieve_documents(query, domain_name)
        logger.debug("Results from retrieve_documents: %s", results)
        if not results:
            return jsonify({'response:': 'No relevant documents found.'}), 404

        # Extract the documents' content for the response
        documents = results['documents'][0] if results['documents'] else []
        context = " ".join(documents)
        response = generate_response(context, query)

        # Return the results directly
        print(response)
        json_response = response.content
        return jsonify({'response': json_response})
    except Exception as e:
        logger.error("Error in /ask endpoint: %s", e)
        return jsonify({"message": "An error occured", "error": str(e)}), 500

@app.route('/submit', methods=['POST'])
def submit_data():
    try:
        logger.debug("Received POST request on /submit endpoint")
        data = request.get_json()
        document = data.get('request', {}).get('document')
        domain_name = data.get('request', {}).get('domain_name')

        # Ensure domain_name is a string
        if isinstance(domain_name, list) and len(domain_name) > 0:
            domain_name = domain_name[0]
        elif not isinstance(domain_name, str):
            domain_name = str(domain_name)

        logger.debug("Data received: %s", data)
        logger.info("Document: %s", document)
        logger.info("Domain name: %s", domain_name)

        # Store domain_name in the session
        session[f"domain_name_{domain_name}"] = domain_name

        # Process the data
        success = process_document(document, domain_name)

        if success:
            logger.debug("Data processed successfully")
            return jsonify({"message": "Data processed successfully."}), 200
        else:
            logger.error("Data processing failed")
            return jsonify({"message": "Data processing failed."}), 500
    except Exception as e:
        logger.error("Error in /submit endpoint: %s", e)
        return jsonify({"message": "An error occured", "error": str(e)}), 500

@app.route('/capture_domain', methods=['POST'])
def capture_domain():
    data = request.get_json()
    domain_name = data.get('domain_name')

    # Ensure domain is a string
    if isinstance(domain_name, list) and len(domain_name) > 0:
        domain_name = domain_name[0]
    elif not isinstance(domain_name, str):
        domain_name = str(domain_name)

    logger.debug("Receiving domain: %s", domain_name)

    # Store domain_name in the session
    session[f"domain_name_{domain_name}"] = domain_name

    # Log session data
    logger.debug("Session data: %s", session.items())

    logger.debug("Domain found and stored in session")
    return jsonify({"message": "Domain stored succesfully"}), 200


@app.route('/<path:path>')
def static_proxy(path):
    file_name = path.split('/')[-1]
    dir_name = '/'.join(path.split('/')[:-1])
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
