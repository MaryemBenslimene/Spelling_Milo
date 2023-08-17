
import lambdaTTS
import lambdaSpeechToScore
import lambdaGetSample
import base64
import io
import base64
import io
from flask import Flask
from flask import request
from flask import Response
import json
import base64

application = Flask(__name__) 


@application.route('/model/spelling', methods=['POST'])
def execute_spelling():

    language = 'en'
    encode_string = request.get_json().get("voice")
    title = request.get_json().get("title")

    wav_file = open("hearing.wav", "wb")
    decode_string = base64.b64decode(encode_string)
    wav_file.write(decode_string)

    sentence_to_read = lambdaGetSample.lambda_handler(language)
    #print("Sentence to read : ", sentence_to_read['real_transcript'][0])
    #print("Phonetics : ", sentence_to_read['ipa_transcript'])
    #title = 'That isnt how most people do that.'
    #print("Sentence to read : ", sentence_to_read['real_transcript'][0])

    lambdaTTS.lambda_handler(title)


    speech_to_score = lambdaSpeechToScore.lambda_handler(title, language)

    #print("Final result:", speech_to_score)
    return Response(json.dumps({'result': speech_to_score }),
                    status=200,
                    mimetype="application/json")
    #return "Hello from milo"

	
if __name__ == '__main__':
    application.run(host='0.0.0.0', port=3000,debug=False)








