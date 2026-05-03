import os
import boto3
from flask import Flask, jsonify, request
from botocore.exceptions import ClientError

app = Flask(__name__)

# Config injected by Kubernetes ConfigMap
REGION = os.environ.get("AWS_REGION", "ap-south-2")

# DynamoDB — credentials come from IRSA, no keys in code
dynamodb = boto3.resource("dynamodb", region_name=REGION)
courses_table = dynamodb.Table("course-amar")


@app.route("/health")
def health():
    # Kubernetes readiness + liveness probe endpoint
    return jsonify({"status": "ok", "service": "course-service"}), 200


@app.route("/courses/<course_id>", methods=["GET"])
def get_course(course_id):
    resp = courses_table.get_item(Key={"id": course_id})
    item = resp.get("Item")
    if not item:
        return jsonify({"error": "Course not found"}), 404
    return jsonify(item), 200


@app.route("/courses", methods=["GET"])
def list_courses():
    resp = courses_table.scan(Limit=50)
    return jsonify(resp.get("Items", [])), 200


@app.route("/courses", methods=["POST"])
def add_course():
    try:
        data = request.get_json()

        # Validation: require code + course_name
        if not data or "code" not in data or "course_name" not in data:
            return jsonify({"error": "Missing required fields: code, course_name"}), 400

        # Map request fields to DynamoDB schema
        item = {
            "id": data["code"],             # DynamoDB partition key
            "name": data["course_name"]     # Store course_name into 'name' column
        }

        # Prevent overwrite if course already exists
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
