import sys
sys.path.insert(0, ".")
from pipeline import GROQ_API_KEY
from groq import Groq

client = Groq(api_key=GROQ_API_KEY)
models = client.models.list()
for m in models.data:
    print(m.id)
