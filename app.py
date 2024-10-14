import streamlit as st
import pandas as pd
from PIL import Image
import datetime as dt
import pyodbc
import os
from azure.storage.blob import BlobServiceClient
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

st.set_page_config(page_title="Provider Wellness Result Submission Portal", page_icon=":hospital:", layout="wide")

image = Image.open('image.png')
st.image(image, use_column_width=True)

server = os.environ.get('servername')
database = os.environ.get('db_name')
username = os.environ.get('db_username')
password = os.environ.get('db_password')
conn_str = os.environ.get('conn_str')


conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};SERVER='
        + server
        +';DATABASE='
        + database
        +';UID='
        + username
        +';PWD='
        + password
        )

# conn = pyodbc.connect(
#         'DRIVER={ODBC Driver 17 for SQL Server};SERVER='
#         +st.secrets['server']
#         +';DATABASE='
#         +st.secrets['database']
#         +';UID='
#         +st.secrets['username']
#         +';PWD='
#         +st.secrets['password']
#         )

query1 = "SELECT * from vw_wellness_enrollee_portal"
query2 = "select MemberNo, MemberName, Client, email, state, selected_provider, Wellness_benefits, selected_date, selected_session, date_submitted,\
        IssuedPACode, PA_Tests, PA_Provider, PAissueDate\
        FROM tbl_annual_wellness_enrollee_data\
        where IssuedPACode is not null and date_submitted >= '2024-10-01'"
query3 = 'select a.*, name as ProviderName\
        from updated_wellness_providers a\
        left join [dbo].[tbl_ProviderList_stg] b\
        on a.code = b.code'
query4 = 'SELECT * FROM tbl_enrollee_wellness_result_data'

@st.cache_data(ttl = dt.timedelta(hours=4))
def get_data_from_sql():
    wellness_df = pd.read_sql(query1, conn)
    wellness_providers = pd.read_sql(query3, conn)
    filled_wellness_df = pd.read_sql(query2, conn)
    # conn.close()
    return wellness_df, wellness_providers, filled_wellness_df

wellness_df, wellness_providers, filled_wellness_df = get_data_from_sql()

filled_wellness_df['ProviderName'] = filled_wellness_df['selected_provider'].str.split('-').str[0].str.strip()
filled_wellness_df['MemberNo'] = filled_wellness_df['MemberNo'].astype(str)

submitted_result_df = pd.read_sql(query4, conn)
submitted_result_df['memberno'] = submitted_result_df['memberno'].astype(str)

# Define a function to apply styles
def highlight_status(status):
    if status == 'Submitted':
        return 'background-color: green; color: white;'
    elif status == 'Not Submitted':
        return 'background-color: red; color: white;'
    return ''

def login_user(username,password):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tbl_provider_wellness_submission_portal_users WHERE code = ?", username)
    user = cursor.fetchone()
    if user:
        if password:
            return user[0], user[1], user[2]
        else:
            return None, None, None
    else:
        return None, None, None
    # return None, None

# Initialize session state variables if they don't exist
if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None
if 'ProviderName' not in st.session_state:
    st.session_state['ProviderName'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None
if 'password' not in st.session_state:
    st.session_state['password'] = None

if st.session_state['authentication_status']:
    st.title("Provider Wellness Result Submission Portal")
    st.write(f"You are currently logged in as {st.session_state['ProviderName']} ({st.session_state['username']})")

    st.sidebar.title("Navigation")
    #returns the list of enrollees for the provider based on the login credentials
    st.sidebar.write("Welcome to the Provider Wellness Result Submission Portal")
    # st.sidebar.write("Please select an option from the sidebar to proceed")
    selected_option = st.sidebar.radio(label="Please select an option to proceed",options=['View Wellness Enrollees and Benefits', 'Submit Wellness Results'])
    if st.session_state['ProviderName'] == 'CLINA LANCET LABOURATORIES':
        provider_df = filled_wellness_df[filled_wellness_df['ProviderName'].str.contains('CERBA LANCET NIGERIA')]
    elif st.session_state['ProviderName'] == 'AVON MEDICAL PRACTICE':
        provider_df = filled_wellness_df[filled_wellness_df['ProviderName'].str.contains('AVON')]
    elif st.session_state['ProviderName'] == 'UNION DIAGNOSTICS AND CLINICAL SERVICES':
        provider_df = filled_wellness_df[filled_wellness_df['ProviderName'].str.contains('UNION')]
    elif st.session_state['ProviderName'] == 'CITRON HEALTH LIMITED':
        provider_df = filled_wellness_df[filled_wellness_df['ProviderName'].str.contains('CITRON')]
    elif st.session_state['ProviderName'] ==  'JJANED SPECIALIST HOSPITAL':
        provider_df = filled_wellness_df[filled_wellness_df['ProviderName'].str.contains('JJANED')]
    elif st.session_state['ProviderName'] ==  'YOBE STATE SPECIALIST HOSPITAL, DAMATURU (GEN. SANNI ABACHA SPECIALIST HOSPITAL, DAMATURU)':
        provider_df = filled_wellness_df[filled_wellness_df['ProviderName'].str.contains('ABACHA')]
    else:
        provider_df = filled_wellness_df[filled_wellness_df['ProviderName'] == st.session_state['ProviderName']]
        #return only the 'MemberNo', 'MemberName', and 'Wellness_benefits' columns
    provider_df = provider_df[['MemberNo', 'MemberName', 'IssuedPACode', 'Wellness_benefits']]
    #create a new column to display if an enrollee result has been submitted or not
    provider_df['SubmissionStatus'] = provider_df['MemberNo'].apply(
    lambda x: 'Submitted' if x in submitted_result_df['memberno'].values else 'Not Submitted')
    provider_df = provider_df.sort_values(by='SubmissionStatus').reset_index(drop=True)
    if selected_option == 'View Wellness Enrollees and Benefits':
        styled_df = provider_df.style.applymap(
        highlight_status, subset=['SubmissionStatus']
    )
        st.subheader("View Wellness Enrollees and Benefits")
        st.write(styled_df)
    elif selected_option == 'Submit Wellness Results':
        st.subheader("Submit Wellness Results")
        not_submitted_df = provider_df[provider_df['SubmissionStatus'] == 'Not Submitted']
        not_submitted_df['member'] = not_submitted_df['MemberNo'].str.cat(not_submitted_df['MemberName'], sep=' - ')
        member_list = not_submitted_df['member'].unique()
        st.write("Please select the enrollee you would like to submit wellness results for")
        member = st.selectbox('Select Enrollee', placeholder='Select Enrollee', index=None, options=member_list)
        #extract the member number from member
        if member:
            member_no = member.split(' - ')[0]
            st.write("Please enter the PACode issued for the Enrollee Wellness Test")
            pa_code = st.text_input("Enter PACode")
            st.write("Please Select the Tests Conducted on the Enrollee")
            tests_conducted = st.multiselect("Select all Tests Conducted", options=['Physical Exam', 'Urinalysis', 'PCV', 'Blood Sugar', 'BP', 'Genotype', 'BMI',
                                                                                'Chest X-Ray', 'Cholesterol', 'Liver Function Test', 'Electrolyte, Urea and Creatinine Test(E/U/Cr)',
                                                                                'Stool Microscopy', 'Mammogram', 'Prostrate Specific Antigen(PSA)', 'Cervical Smear'])
            st.write("Please Enter the Date the Tests were Conducted")
            test_date = st.date_input("Enter Test Date")

            name = filled_wellness_df[filled_wellness_df['MemberNo'] == member_no]['MemberName'].values[0]
            #create a image uploader for the test results
            uploaded_file = st.file_uploader("Upload Test Results", accept_multiple_files=True)
            #store the uploaded files in a blob storage and return the url

            # Initialize the BlobServiceClient
            # blob_service_client = BlobServiceClient.from_connection_string(st.secrets['conn_str'])
            blob_service_client = BlobServiceClient.from_connection_string(conn_str)
            # Create a single container for all uploaded images
            container_name = 'annual-wellness-results'
            container_client = blob_service_client.get_container_client(container_name)
            if uploaded_file is not None:
                #get the client and provider names
                client_name = filled_wellness_df[filled_wellness_df['MemberNo'] == member_no]['Client'].values[0].replace(" ", "").lower()
                provider_name = st.session_state['ProviderName'].replace(" ", "").lower()

                # Get the current year and create a subfolder for each year in each provider folder
                current_year = datetime.now().year
                year_folder = f"{client_name}/{current_year}/{provider_name}"
                member_folder = f"{year_folder}/{member}"

                # List to hold the URLs of uploaded files
                uploaded_urls = []

                for file in uploaded_file:
                    # Create a unique name for the file using the original file name
                    unique_filename = f"{member_no}_{file.name}"
                    blob_path = f'{member_folder}/{unique_filename}'

                    # # Full path to upload the file
                    # blob_path = os.path.join(member_folder, unique_filename)

                    # Get the blob client using the full path
                    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_path)
                    
                    # Upload the file
                    blob_client.upload_blob(file, overwrite=True)

                    # Get the URL of the uploaded file and add it to the list
                    uploaded_urls.append(blob_client.url)

                # URL pointing to the member's folder (just for reference, not an actual browseable URL)
                member_folder_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{member_folder}"

                if st.button("Submit Results"):
                    #write the details of the enrollee submission to a table in the database    
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO tbl_enrollee_wellness_result_data (\
                                memberno, membername, providername, pacode, tests_conducted, test_date, test_result_link)\
                                    VALUES (?, ?, ?, ?, ?, ?, ?)", member_no, name, st.session_state['ProviderName'], pa_code, ', '.join(tests_conducted), test_date, member_folder_url)
                    conn.commit()

                    #send an email to the enrollee with an attachment of the test results
                    myemail = 'noreply@avonhealthcare.com'
                    # password = st.secrets['emailpassword']
                    password = os.environ.get('emailpassword')
                    email = filled_wellness_df[filled_wellness_df['MemberNo'] == member_no]['email'].values[0]
                    bcc_email = 'ademola.atolagbe@avonhealthcare.com'
                    # email = filled_wellness_df[filled_wellness_df['MemberNo'] == member_no]['email'].values[0]
                    subject = "AVON HMO ANNUAL WELLNESS TEST RESULTS"
                    body = f'''
                            Dear {name},<br><br>
                            Trust this message meets you well.<br><br>
                            Following your recent wellness test at {st.session_state['ProviderName']} on {test_date},<br>
                            Please find attached the results of the wellness tests conducted on you.<br><br>
                            You are advised to review the results and consult with your primary healthcare provider for further advice.<br><br>
                            Please ensure that you follow the advice provided by your healthcare provider to maintain a healthy lifestyle.<br><br>
                            Best Regards,<br>
                            AVON HMO Medical Services
                            '''
                    attachment = uploaded_file
                    #send_email(email, subject, body, attachment)
                    try:
                        server = smtplib.SMTP('smtp.office365.com', 587)
                        server.starttls()

                        #login to outlook account
                        server.login(myemail, password)

                        #create a MIMETesxt object for the email message
                        msg = MIMEMultipart()
                        msg['From'] = 'AVON HMO Medical Services'
                        msg['To'] = email
                        msg['Bcc'] = bcc_email
                        msg['Subject'] = subject
                        msg.attach(MIMEText(body, 'html'))
                        #attach the file to the email
                        for file in uploaded_file:
                            file.seek(0)
                            file_data = file.read()
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(file_data)
                            encoders.encode_base64(part)
                            part.add_header('Content-Disposition', f'attachment; filename={file.name}')
                            msg.attach(part)

                        #send the email
                        recipient = [email, bcc_email]
                        server.sendmail(myemail, recipient, msg.as_string())
                        server.quit()
                    except Exception as e:
                        st.error(f"An error occurred: {e}")
                    
                    st.success('Results Submitted Successfully a copy of the results has been sent to the enrollee')    
        else:
            st.error("Select an Enrollee to Proceed")    

    with st.sidebar:
        if st.button('Logout'):
            st.session_state['ProviderName'] = None
            st.session_state['username'] = None
            st.session_state['authentication_status'] = None
            st.experimental_rerun()
else:
    # Display the login page
    st.title("Home Page")
    st.write("Login with your username and password to access the portal.")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user_name, providername, login_password = login_user(username, password)
        if user_name == username and password == login_password:
            st.session_state['ProviderName'] = providername
            st.session_state['authentication_status'] = True
            st.session_state['username'] = username
            st.session_state['password'] = password
            st.experimental_rerun()
        else:
            st.error("Username/password is incorrect")