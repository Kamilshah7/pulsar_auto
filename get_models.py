from secrets_loader import get_secret
import os
from groq import Groq
client = Groq(api_key=get_secret("GROQ_API_KEY"))
models = client.models.list()
print([m.id for m in models.data if "llama" in m.id])
