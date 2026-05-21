"""
knowledge_base.py
-----------------
20 text chunks across 5 topic areas.
Each chunk: { chunkId, doc, text }
"""

CHUNKS = [
    # Python
    {"chunkId": "py-001", "doc": "Python Basics",
     "text": "Python is a high-level, interpreted programming language known for clear syntax and readability. It supports procedural, object-oriented, and functional programming paradigms."},
    {"chunkId": "py-002", "doc": "Python Basics",
     "text": "Python uses indentation to define code blocks instead of curly braces, enforcing a consistent and readable code style across all projects."},
    {"chunkId": "py-003", "doc": "Python Libraries",
     "text": "The Python standard library includes modules for file I/O, networking, JSON serialization, regular expressions, threading, and many other common programming tasks."},
    {"chunkId": "py-004", "doc": "Python Libraries",
     "text": "Popular third-party Python libraries include NumPy and Pandas for data analysis, TensorFlow and PyTorch for machine learning, Flask and FastAPI for web APIs, and Requests for HTTP."},
    # Machine Learning
    {"chunkId": "ml-001", "doc": "ML Overview",
     "text": "Machine learning is a subset of AI where algorithms learn patterns from data to make predictions or decisions without being explicitly programmed for each specific task."},
    {"chunkId": "ml-002", "doc": "ML Overview",
     "text": "Supervised learning trains on labeled data, unsupervised learning finds patterns in unlabeled data, and reinforcement learning trains agents using reward signals from an environment."},
    {"chunkId": "ml-003", "doc": "Neural Networks",
     "text": "A neural network consists of layers of interconnected nodes. Each connection has a weight adjusted during training to minimize the loss function via backpropagation and gradient descent."},
    {"chunkId": "ml-004", "doc": "Neural Networks",
     "text": "Deep learning uses many-layered neural networks. CNNs excel at image recognition, RNNs handle sequential data, and Transformers power modern NLP and large language models."},
    # RAG & LLMs
    {"chunkId": "rag-001", "doc": "RAG Overview",
     "text": "Retrieval-Augmented Generation (RAG) combines a retrieval system with a language model. The retriever fetches relevant chunks from a knowledge base; the LLM uses them as context to generate accurate answers."},
    {"chunkId": "rag-002", "doc": "RAG Overview",
     "text": "RAG reduces LLM hallucinations by grounding responses in retrieved facts. It also allows models to access current information without costly retraining or fine-tuning."},
    {"chunkId": "rag-003", "doc": "Vector Databases",
     "text": "Vector databases store documents as high-dimensional embeddings. Similarity search using cosine distance or dot-product retrieves the most semantically relevant chunks for a given query."},
    {"chunkId": "rag-004", "doc": "Vector Databases",
     "text": "Popular vector databases include Pinecone, Weaviate, Chroma, and FAISS. They support approximate nearest-neighbour search for fast, scalable retrieval across millions of documents."},
    # Software Engineering
    {"chunkId": "se-001", "doc": "SE Principles",
     "text": "SOLID is five OOP design principles: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, and Dependency Inversion. They improve maintainability and reduce coupling."},
    {"chunkId": "se-002", "doc": "SE Principles",
     "text": "Test-Driven Development (TDD) requires writing a failing test before writing implementation code. This ensures correctness, promotes good design, and produces a comprehensive regression test suite."},
    {"chunkId": "se-003", "doc": "REST APIs",
     "text": "REST uses HTTP methods: GET retrieves resources, POST creates them, PUT replaces them, PATCH partially updates them, and DELETE removes them. Resources are identified by URLs."},
    {"chunkId": "se-004", "doc": "REST APIs",
     "text": "API versioning via path prefixes like /v1/ or /v2/ allows backward-compatible evolution. Common auth mechanisms include API keys, OAuth 2.0 bearer tokens, and signed JWTs."},
    # Cloud & DevOps
    {"chunkId": "cloud-001", "doc": "Cloud Computing",
     "text": "Cloud computing delivers computing resources on demand over the internet. The three service models are IaaS (Infrastructure), PaaS (Platform), and SaaS (Software) as a Service."},
    {"chunkId": "cloud-002", "doc": "Cloud Computing",
     "text": "The three major cloud providers are AWS, Microsoft Azure, and Google Cloud Platform. They offer compute, storage, managed databases, AI/ML services, and global networking infrastructure."},
    {"chunkId": "devops-001", "doc": "CI/CD",
     "text": "CI/CD automates building, testing, and deploying software. Continuous Integration merges code frequently; Continuous Deployment ships passing builds automatically. Tools include GitHub Actions, Jenkins, and GitLab CI."},
    {"chunkId": "devops-002", "doc": "Containers",
     "text": "Docker packages applications into portable containers with all dependencies. Kubernetes orchestrates containers at scale, providing automated deployment, horizontal scaling, load balancing, and self-healing."},
]


def get_all_chunks() -> list[dict]:
    return CHUNKS
