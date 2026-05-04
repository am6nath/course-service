import os
import boto3
from flask import Flask, jsonify, request
from botocore.exceptions import ClientError
from flask_cors import CORS   # <-- NEW

app = Flask(__name__)

# Enable CORS for your frontend URL
CORS(app, origins=["http://course-frontend-amar.s3-website.ap-south-2.amazonaws.com"])

# AWS region injected via Kubernetes ConfigMap/Env
REGION = os.environ.get("AWS_REGION", "ap-south-2")

# DynamoDB resource (credentials via IRSA, no keys in code)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
courses_table = dynamodb.Table("course-amar")

# --- Routes remain unchanged ---
@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "course-service"}), 200

@app.route("/courses/<course_id>", methods=["GET"])
def get_course(course_id):
    try:
        resp = courses_table.get_item(Key={"id": course_id})
        item = resp.get("Item")
        if not item:
            return jsonify({"error": "Course not found"}), 404
        return jsonify(item), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/courses", methods=["GET"])
def list_courses():
    try:
        resp = courses_table.scan(Limit=50)
        return jsonify(resp.get("Items", [])), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/courses", methods=["POST"])
def add_course():
    try:
        data = request.get_json()
        if not data or "code" not in data or "course_name" not in data:
            return jsonify({"error": "Missing required fields: code, course_name"}), 400

        item = {
            "id": data["code"],
            "name": data["course_name"]
        }

        courses_table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(id)"
        )

        return jsonify({"message": "Course added successfully", "course": item}), 201

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return jsonify({"error": "Course already exists"}), 409
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001, debug=False)
