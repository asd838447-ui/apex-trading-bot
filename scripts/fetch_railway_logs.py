import os
import requests
import json
import sys

TOKEN = "1e07b7e0-c435-4030-9f5e-d4487262e01e"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def run_query(query, variables=None):
    request = requests.post(
        "https://backboard.railway.app/graphql/v2",
        json={"query": query, "variables": variables or {}},
        headers=HEADERS
    )
    if request.status_code == 200:
        res = request.json()
        if 'errors' in res:
            print("GraphQL Errors:", json.dumps(res['errors'], indent=2))
            sys.exit(1)
        return res
    else:
        print(f"Query failed: {request.status_code} {request.text}")
        sys.exit(1)

projects_query = """
query {
  me {
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
"""

print("Testing authentication and fetching projects...")
res = run_query(projects_query)
print("Raw Response:", json.dumps(res, indent=2))
