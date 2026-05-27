import requests
import json
import sys

TOKEN = "1e07b7e0-c435-4030-9f5e-d4487262e01e"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

query = """
query {
  teams {
    edges {
      node {
        id
        name
        projects {
          edges {
            node {
              id
              name
              environments {
                edges {
                  node {
                    id
                    name
                  }
                }
              }
              services {
                edges {
                  node {
                    id
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

request = requests.post(
    "https://backboard.railway.app/graphql/v2",
    json={"query": query},
    headers=HEADERS
)

print(json.dumps(request.json(), indent=2))
