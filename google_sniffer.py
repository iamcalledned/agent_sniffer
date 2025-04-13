import os
import json
import requests
from dotenv import load_dotenv
from openai import OpenAI

# Load credentials
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# Load assistant config
with open("news_sniffer_config.json", "r") as f:
    assistant_config = json.load(f)

ASSISTANT_ID = assistant_config["id"]

def fetch_google_results(query, num_results=10):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": num_results
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    data = res.json()

    results = []
    for item in data.get("items", []):
        results.append({
            "title": item.get("title"),
            "link": item.get("link"),
            "snippet": item.get("snippet")
        })

    return results


def build_prompt(query, results):
    prompt = f"Topic: {query}\n\n"
    prompt += "Here are the most relevant news headlines from today:\n\n"

    for i, item in enumerate(results, 1):
        prompt += (
            f"{i}. {item['title']}\n"
            f"URL: {item['link']}\n"
            f"Summary: {item['snippet']}\n\n"
        )

    prompt += (
        "\nActivate your macro-financial news scanning capabilities. "
        "Your task is to identify and summarize the most important recent developments across global markets, "
        "monetary policy, credit conditions, volatility, and systemic risk. Focus on news that could materially shift the market’s risk environment. "
        "Return a list of structured JSON objects with the following fields:\n\n"
        "- headline: Title of the article or news item\n"
        "- source: Publisher or analyst name\n"
        "- url: Direct link to the article\n"
        "- timestamp: Date and time of publication (if available, UTC preferred)\n"
        "- summary: 1–3 concise bullet points explaining the significance\n"
        "- category: One or more tags relevant to Bottom Sniffer components (e.g., 'Rates & Curve', 'Credit & Volatility', 'Macro Indicators', 'Flight to Safety')\n"
        "- sentiment: Market signal ('Risk-On', 'Neutral', or 'Risk-Off') based on the article's implications\n\n"
        "Only return content that impacts the risk assessment framework, market stress indicators, or trading posture. "
        "Filter out low-signal items and focus on actionable macro and systemic developments."
    )

    return prompt


def run_news_sniffer(query):
    print(f"🔍 Searching for: {query}")
    results = fetch_google_results(query)

    print(f"📡 Found {len(results)} articles. Passing to NewsSniffer...")

    thread = client.beta.threads.create()

    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=build_prompt(query, results)
    )

    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=ASSISTANT_ID
    )

    # Wait for completion
    while True:
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run.status == "completed":
            break

    messages = client.beta.threads.messages.list(thread_id=thread.id)
    for msg in reversed(messages.data):
        response = msg.content[0].text.value.strip()
        print("\n🧠 NewsSniffer Output:\n")
        print(response)

        try:
            parsed = json.loads(response)
            with open("sniffer_output.json", "w") as f:
                json.dump(parsed, f, indent=2)
            print("\n✅ Output saved to sniffer_output.json")
        except json.JSONDecodeError:
            print("\n⚠️ Could not parse output as JSON. Manual review required.")
            with open("sniffer_output_raw.txt", "w") as f:
                f.write(response)
            print("📝 Raw response saved to sniffer_output_raw.txt")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python google_sniffer.py \"your search query here\"")
    else:
        query = " ".join(sys.argv[1:])
        run_news_sniffer(query)
