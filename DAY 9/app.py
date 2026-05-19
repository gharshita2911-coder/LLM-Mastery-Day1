from flask import Flask,request,jsonify
from Agent import run_agent
app=Flask(__name__)

@app.route("/")
def home():
    return jsonify({"message":"AI Agent running"})

@app.route("/ask",methods=["POST"])
def ask():
    try:
        data=request.get_json()
        message=data.get("message")

        if not message:
            return jsonify({
                "error":"Message required"
            }),400
        response=run_agent(message)
        return jsonify(response)
    except Exception as e:
        return jsonify({
            "error":str(e)
        }),500

if __name__=="__main__":
    app.run(debug=True,port=5000)