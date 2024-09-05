import streamlit as st
import boto3
import time
import os

aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_region = os.getenv('AWS_REGION')

my_session = boto3.session.Session(
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_region
)

if 'uploaded' not in st.session_state:
    st.session_state.uploaded = False


def reset_state():
    st.session_state.uploaded = False


# Constants
S3BUCKET = "videouploadedfile"

st.title('Image and Video Analysis App')

analysisType = st.radio(
    "Please choose the type of analysis",
    ["Image", "Video"],
    index=None,
    on_change=reset_state
)

if analysisType is "Image":

    data = st.file_uploader('Upload the Image you want to analyse here!', type=['png', 'jpg'])
    if data is not None:
        bytes_data = data.getvalue()
        st.image(data)


    def detectface():

        client = my_session.client("rekognition")

        response = client.detect_faces(
            Image={
                'Bytes': bytes_data
            },
            # MaxLabels=100,
            # MinConfidence=minValue,
            Attributes=['ALL']
        )
        return response['FaceDetails']


    def detectlabel(minValue, maxLabel):

        client = my_session.client("rekognition")

        response = client.detect_labels(
            Image={
                'Bytes': bytes_data
            },
            MaxLabels=maxLabel,
            MinConfidence=minValue
        )
        return response['Labels']


    button = st.radio(
        "Please choose the type of analysis",
        ["Labels", "Faces"],
        index=None,
    )

    if button is "Labels":
        minValue = st.slider("Please select minimum confidence level:", 1, 100, 80, 10)
        maxLabel = st.number_input("Please enter number of labels wanted: (max: 1000)", min_value=1, value=100, step=1,
                                   format="%d",
                                   max_value=1000)
        if st.button("Analyze Labels"):
            for label in detectlabel(minValue, maxLabel):
                st.write("{Name} - {Confidence}%".format(**label))

    if button is "Faces":
        FEATURES_BLACKLIST = None

        if st.button("Analyze Faces"):
            for face in detectface():
                st.write(
                    "Face ({Confidence}%)".format(**face))
                # emotions
                for emotion in face['Emotions']:
                    st.write(
                        "  {Type} : {Confidence}%".format(**emotion))

                if FEATURES_BLACKLIST is not None:
                    for feature, data in face.iteritems():
                        if feature not in FEATURES_BLACKLIST:
                            st.write(
                                "  {feature}({data[Value]}) : {data[Confidence]}%".format(feature=feature, data=data))
# VIDEO ----------------------------------------------------------------------------------------------------------

if analysisType is "Video":
    uploaded_file = st.file_uploader(
            label="Choose a file",
            type=["mp4"],
            key="uploaded_file",
            on_change=reset_state
    )
    if uploaded_file is not None and not st.session_state.uploaded:
        s3 = boto3.client("s3")
        s3.upload_fileobj(uploaded_file, "videouploadedfile", uploaded_file.name)
        st.session_state.uploaded = True

    # add progress bar when loading to s3

    def StartLabelDetection(dn, bucket, minValue):

        client = my_session.client("rekognition")

        response = client.start_label_detection(
            Video={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': dn,
                }
            },
            MinConfidence=minValue,
            Features=[
                'GENERAL_LABELS',
            ]
        )
        return response


    def GetLabelDetection(id, maxresult):

        client = my_session.client("rekognition")

        response = client.get_label_detection(
            JobId=id,
            MaxResults=maxresult,
            SortBy='TIMESTAMP',
            AggregateBy='TIMESTAMPS'
        )
        return response


    button = st.radio(
        "Please choose the type of analysis",
        ["Labels", "Faces"],
        index=None,
    )


    def StartFaceDetection(dn, bucket):

        client = my_session.client("rekognition")

        response = client.start_face_detection(
            Video={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': dn,
                }
            },
            FaceAttributes='ALL'
        )
        return response


    def GetFaceDetection(id, maxresults):

        client = my_session.client("rekognition")

        response = client.get_face_detection(
            JobId=id,
            MaxResults=maxresults,
        )
        return response


    if button is "Labels" and st.session_state.uploaded is True:
        minValue = st.slider("Please select minimum confidence level:", 1, 100, 80, 10)
        maxLabel = st.number_input("Please enter number of labels wanted: (max: 1000)", min_value=1, value=100, step=10,
                                   format="%d",
                                   max_value=1000)

        if st.button("Analyze Labels"):
            st.divider()
            jobid = StartLabelDetection(uploaded_file.name, S3BUCKET, minValue)['JobId']

            status = None
            with st.spinner('Analyzing Labels, Please wait.'):

                while status is None or status == 'IN_PROGRESS':

                    datadict = {

                    }
                    response = GetLabelDetection(jobid, maxLabel)
                    status = response['JobStatus']

                    if status == 'SUCCEEDED':
                        st.success("Analysis successful")
                        # print this out nicer
                        for label in response['Labels']:
                            ts = label["Timestamp"]
                            lc = {
                                label['Label']['Name']: label['Label']['Confidence']
                            }
                            if ts not in datadict:
                                datadict.update({
                                    ts: lc
                                })
                            elif ts in datadict:
                                datadict[ts].update({
                                    label['Label']['Name']: label['Label']['Confidence']
                                })
                        # Print it out!
                        for x, obj in datadict.items():
                            st.divider()
                            st.write("Timestamp: ", x)

                            for y in obj:
                                st.write("      " + y + ':', obj[y], "%")
                    elif status == 'FAILED':
                        st.error("Failed to analyze")
                    if status == 'IN_PROGRESS':
                        time.sleep(3)

    if button is "Faces" and st.session_state.uploaded is True:
        maxLabel = st.number_input("Please enter number of labels wanted: (max: 1000)", min_value=1, value=100, step=10,
                                   format="%d",
                                   max_value=1000)

        if st.button("Analyze Faces"):
            jobid = StartFaceDetection(uploaded_file.name, S3BUCKET)['JobId']

            status = None
            st.divider()
            with st.spinner('Analyzing Faces, Please wait.'):
                while status is None or status == 'IN_PROGRESS':
                    response = GetFaceDetection(jobid, maxLabel)
                    status = response['JobStatus']
                    datadict = {

                    }
                    if status == 'SUCCEEDED':
                        facecount = 0
                        st.success("Analysis successful")
                        for face in response['Faces']:
                            ts = face["Timestamp"]
                            facesDict = {
                                facecount: {}
                            }

                            if ts not in datadict:
                                datadict.update({
                                    ts: facesDict
                                })
                            elif ts in datadict:
                                datadict[ts].update({
                                    facecount: {}
                                })

                            # emotions
                            if "Emotions" in face["Face"]:
                                for emotion in face['Face']['Emotions']:
                                    emotionsDict = {
                                        emotion['Type']: emotion['Confidence']
                                    }
                                    datadict[ts][facecount].update(emotionsDict)
                            facecount = facecount + 1
                        # print out data

                        for x, face in datadict.items():
                            st.divider()
                            st.write("Timestamp: ", x)

                            for y, emo in face.items():
                                st.write("Face number: ", y)
                                for z in emo:
                                    st.write("      " + z + ':', emo[z], "%")
                    elif status == 'FAILED':
                        st.error("Failed to analyze")
                    if status == 'IN_PROGRESS':
                        time.sleep(3)
    st.divider()
