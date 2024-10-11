import json
import os
import subprocess
import time

import boto3
import sys
import uuid
import string
import random







# -----------------------------------------------------------------------------------------------
# PRECONFIGURATION
# -----------------------------------------------------------------------------------------------
KEY_FILE_LOCATION = "./awsec.pem"
KEY_PAIR_NAME = "awsec"
SECURITY_GROUP_ID = 'sg-048aa87cffa88d78f'
FILE_PATH_TO_INDEX_FILE = "./index.html"
SETUP_RDS = False
SETUP_DOCDB = False # Student account is not permitted to deploy DocumentDB Instance unfortunately, but the code should work itself.






# Source for string gen: https://stackoverflow.com/questions/2257441/random-string-generation-with-upper-case-letters-and-digits
def id_generator(size=6, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

print("--==--StartOfScript--==--")
# -----------------------------------------------------------------------------------------------
# EC2
# -----------------------------------------------------------------------------------------------
print("> Creating EC2 ")
ec2 = boto3.resource('ec2')
try:
    new_instance = ec2.create_instances(
        ImageId='ami-0ebfd941bbafe70c6',
        MinCount=1,
        MaxCount=1,
        InstanceType='t2.nano',
        KeyName=KEY_PAIR_NAME,
        SecurityGroupIds=[SECURITY_GROUP_ID],
        UserData="""#!/bin/bash
        yum update -y 
        yum install httpd -y
        yum install traceroute -y
        yum -y install mariadb-server
        service mariadb start
        systemctl enable mariadb
        systemctl start mariadb
        systemctl enable httpd
        systemctl start httpd
        mysql_secure_installation
        TOKEN=`curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600"`
        echo '<html lang="en"><head><meta charset="utf-8" /><link rel="icon" href="https://cdn-icons-png.flaticon.com/512/5136/5136950.png" /><title>' >> index.html
        curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/instance-id >> index.html
        echo '</title></head>' >> index.html
        echo '<body style="background: black; color: white; font-size: 200%"><br>Instance ID: ' >> index.html
        curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/instance-id >> index.html
        echo '<br>Public IPv4: ' >> index.html
        curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/public-ipv4 >> index.html
        echo '<br>Local IPv4: ' >> index.html
        curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/local-ipv4 >> index.html
        echo '<br>AZ: ' >> index.html
        curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/placement/availability-zone >> index.html
        echo '<br>MAC address (eth0): ' >> index.html
        curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/mac >> index.html
        echo '<br>Instance type: ' >> index.html
        curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/instance-type >> index.html
        echo '<br></body></html>' >> index.html
        cp index.html /var/www/html/index.html""",
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': 'ztoth-devops-ass1'
                    },
                ]
            },
        ])[0]
    print(f"> Instance {new_instance.id} created. Waiting for it to run...")
    new_instance.wait_until_running()
    new_instance.reload()
    print(f"[SUCCESS] Instance {new_instance.id} is now running!")
    print(f"[SUCCESS] IPv4 of newly created instance is: http://{new_instance.public_ip_address}")
except Exception as error:
    print(f"[ ERROR ] An error occurred while creating EC2 instance. {error}")

# -----------------------------------------------------------------------------------------------
# S3
# -----------------------------------------------------------------------------------------------

print("> Starting to create S3 bucket...")
s3 = boto3.resource("s3")

image_url = 'http://devops.witdemo.net/logo.jpg'
image_path = '/tmp/logo.jpg'

bucket_name = f"{id_generator()}-ztoth"  # using UUID instead of the shell commands
file_path = FILE_PATH_TO_INDEX_FILE
object_name = "index.html"
website_configuration = {
    'ErrorDocument': {'Key': 'error.html'},
    'IndexDocument': {'Suffix': 'index.html'},
}
try:
    # Getting the image > Source https://stackoverflow.com/questions/4256107/running-bash-commands-in-python
    os.system(f"curl -o {image_path} {image_url}")
except Exception as error:
    print(f"[ ERROR ] An error occurred while downloading image: {error}")

try:
    bucket = s3.create_bucket(
        Bucket=bucket_name
    )



    bucket_website = s3.BucketWebsite(bucket_name)
    bucket_website.put(WebsiteConfiguration=website_configuration)

    print(f"[SUCCESS] Bucket {bucket_name} created and configured!")



    print("> Uploading index.html file...")
    try:
        s3.Object(bucket_name, object_name).put(Body=open(file_path, 'rb'), ContentType='text/html')
        print(f"[SUCCESS] File {object_name} uploaded successfully!")

        print(f"[SUCCESS] Visit the following URL to check the website: http://{bucket_name}.s3-website-us-east-1.amazonaws.com")
    except Exception as upload_error:
        print(f"[ ERROR ] File upload failed: {upload_error}")




    print("> Uploading image file...")
    try:
        # Upload image it to S3
        # s3.upload_file(image_path, bucket_name, 'logo.jpg')
        s3.Object(bucket_name, 'logo.jpg').put(Body=open(image_path, 'rb'), ContentType='image/jpeg')
        print(f"[SUCCESS] Image uploaded successfully!")

        print(f"[SUCCESS] Visit the following URL to check the image: http://{bucket_name}.s3-website-us-east-1.amazonaws.com/logo.jpg")
    except Exception as upload_error:
        print(f"[ ERROR ] Image upload failed: {upload_error}")




except Exception as bucket_error:
    print(f"[ ERROR ] Bucket creation failed: {bucket_error}")





print(f"> Attempting to set bucket policy to gain public access for s3 website!")
# Source: https://stackoverflow.com/questions/62769338/how-can-i-create-bucket-and-objects-with-not-public-access-using-boto3-in-aws
# https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-example-bucket-policies.html
s3_client = boto3.client('s3')
try:
    # Disable block public access for the bucket
    s3_client.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            'BlockPublicAcls': False,
            'IgnorePublicAcls': False,
            'BlockPublicPolicy': False,
            'RestrictPublicBuckets': False
        }
    )
    print(f"[SUCCESS] Successfully disabled the public access block for the bucket!")
except Exception as public_access_error:
    print(f"[ ERROR ] Error while disabling public access block for the bucket: {public_access_error}")

bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }
        ]
    }
bucket_policy_string = json.dumps(bucket_policy)
try:
    s3.Bucket(bucket_name).Policy().put(Policy=bucket_policy_string)
    print("[SUCCESS] Policy set success!")
except Exception as error:
    print(f"[ ERROR ] Policy set failed: {error}")


# -----------------------------------------------------------------------------------------------
# ztoth-websites.txt write
# -----------------------------------------------------------------------------------------------

print(f"> Initiating URLs writing to txt file")
try:
    cmd1 = "rm ./ztoth-websites.txt && touch ./ztoth-websites.txt"
    subprocess.run(cmd1, shell=True, check=True)

    cmd2 = f"echo 'http://{bucket_name}.s3-website-us-east-1.amazonaws.com' >> ./ztoth-websites.txt"
    subprocess.run(cmd2, shell=True, check=True)

    cmd3 = f"echo 'http://{new_instance.public_dns_name}' >> ./ztoth-websites.txt"
    subprocess.run(cmd3, shell=True, check=True)
    print("[SUCCESS] Success writing to txt file")
except Exception as error:
    print(f"[ ERROR ] Error while writing to txt file: {error}")


# -----------------------------------------------------------------------------------------------
# Extra stuff - MySQL RDBMS setup! https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/rds.html
# -----------------------------------------------------------------------------------------------
if SETUP_RDS == True:
    print(f"> Deploying Relational Database Service")
    rds = boto3.client('rds')
    endpointForDatabase = "NOTSET"
    try:
        database = rds.create_db_instance(
            DBInstanceIdentifier='db-ztoth',
            MasterUsername='admin',
            MasterUserPassword='adminadmin',  # Very creative pwd isn't it?
            DBInstanceClass='db.t3.micro',  # https://aws.amazon.com/rds/instance-types/
            Engine='mysql',
            AllocatedStorage=20,  # in GB
            PubliclyAccessible=True
        )
        waiter = rds.get_waiter('db_instance_available')
        waiter.wait(
            DBInstanceIdentifier='db-ztoth')  # This takes ages: https://www.reddit.com/r/Terraform/comments/suxw1t/why_does_deploying_an_rds_db_take_so_long/
        # https://www.reddit.com/r/Terraform/comments/suxw1t/why_does_deploying_an_rds_db_take_so_long/
        db_instance_info = rds.describe_db_instances(DBInstanceIdentifier='db-ztoth')
        endpointForDatabase = db_instance_info['DBInstances'][0]['Endpoint']['Address']
        print(f"[SUCCESS] Database service created! ENDPOINT: {endpointForDatabase}")
    except Exception as error:
        print(f"[ ERROR ] Unable to create the database: {error}")
else:
    print(f"> RDS is not set to deploy")


# -----------------------------------------------------------------------------------------------
# Extra stuff 2 - DocumentDB https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/docdb.html
# -----------------------------------------------------------------------------------------------
# HAS ISSUE
# Access denied
# You don't have permission to iam:GetRole. To request access, copy the following text and send it to your AWS administrator. Learn more about troubleshooting access denied errors.
# User: arn:aws:sts::574555277277:assumed-role/voclabs/user3504676=Zalan_Toth
# Action: iam:GetRole
# Context: an identity-based policy explicitly denies the action
# The code should be somewhat right, however there's no auto deletion like on other services as I'm not able to test it.

if SETUP_DOCDB == True:
    print(f"> Deploying DocumentDB Service")
    docdb_client = boto3.client('docdb')
    db_cluster_identifier = 'ztoth-cluster'
    db_instance_identifier = 'ztoth-instance'
    master_username = 'ztoth'
    master_user_password = 'adminadmin'

    print(f"> Creating DocumentDB Cluster")
    try:
        docdbcluster = docdb_client.create_db_cluster(
            DBClusterIdentifier=db_cluster_identifier,
            Engine='docdb',
            MasterUsername=master_username,
            MasterUserPassword=master_user_password,
            VpcSecurityGroupIds=[SECURITY_GROUP_ID],
            DBSubnetGroupName='default',  # The default one!
            BackupRetentionPeriod=7,
            PreferredBackupWindow='07:00-09:00'
        )
    except Exception as error:
        print(f"[ ERROR ] Unable to create cluster: {error}")

    print(f"> Creating DocumentDB Instance")
    try:
        docdbinstance = docdb_client.create_db_instance(
            DBInstanceIdentifier=db_instance_identifier,
            DBClusterIdentifier=db_cluster_identifier,
            Engine='docdb',
            DBInstanceClass='db.t3.micro',
            PreferredMaintenanceWindow='sat:03:00-sat:04:00'
        )
    except Exception as error:
        print(f"[ ERROR ] Unable to create docdb instance: {error}")
else:
    print(f"> DocumentDB is not set to deploy")

# -----------------------------------------------------------------------------------------------
# monitor.sh
# -----------------------------------------------------------------------------------------------

print(f"> Initiating uploading and running monitoring file")
try:
    time.sleep(35)
    cmd11 = f"ssh -i {KEY_FILE_LOCATION} -o StrictHostKeyChecking=no ec2-user@{new_instance.public_ip_address} 'uname -a'"
    subprocess.run(cmd11, shell=True, check=True)

    #if setupdb == True:
    #    cmd10 = f"ssh -i {KEY_FILE_LOCATION} ec2-user@{new_instance.public_ip_address} 'mysql -h {endpointForDatabase} -u admin -padminadmin \"CREATE DATABASE devops;SHOW DATABASES;\"'"
    #    subprocess.run(cmd10, shell=True, check=True)


    cmd12 = f"scp -i {KEY_FILE_LOCATION} monitoring.sh ec2-user@{new_instance.public_ip_address}:."
    subprocess.run(cmd12, shell=True, check=True)

    cmd13 = f"ssh -i {KEY_FILE_LOCATION} ec2-user@{new_instance.public_ip_address} 'chmod +x ./monitoring.sh && ./monitoring.sh'"
    subprocess.run(cmd13, shell=True, check=True)



    print("[SUCCESS] Monitoring script executed successfully")
except Exception as error:
    print(f"[ ERROR ] Monitoring script failed due to: {error}")



# -----------------------------------------------------------------------------------------------
# COMPLETION
# -----------------------------------------------------------------------------------------------

print("""-----------------------------
SETUP COMPLETED
-----------------------------""")


# -----------------------------------------------------------------------------------------------
# CLEANUP IF NECESSARY
# -----------------------------------------------------------------------------------------------

if len(sys.argv) > 1 and sys.argv[1] == '1':
    print("[   !   ] First argument is 1, which means that the machine and s3 storage is initiated to be terminated and deleted 1 minute after setup completion")
    time.sleep(30)  # Wait for 1 minute
    print("[   !   ] Cleanup begins!")
    try:
        print(f"> Deleting EC2 instance! Be patient. ({new_instance.id})")
        new_instance.terminate()
        new_instance.wait_until_terminated()
        print(f"[SUCCESS] Termination success for instance {new_instance.id}")
    except Exception as error:
        print(f"[ ERROR ] Error while terminating EC2 instance: {error}")
    try:
        print(f"> Deleting S3 bucket {bucket_name}!")
        bucket = s3.Bucket(bucket_name)
        bucket.objects.all().delete()
        bucket.delete()
        print(f"[SUCCESS] S3 bucket {bucket_name} has been emptied and deleted successfully")
    except Exception as error:
        print(f"[ ERROR ] Error while deleting S3 bucket {bucket_name}: {error}")

    if SETUP_RDS == True:
        try:
            print("> Deleting RDS...")
            rds.delete_db_instance(
                DBInstanceIdentifier='db-ztoth',
                SkipFinalSnapshot=True
            )
            waiter = rds.get_waiter('db_instance_deleted')
            waiter.wait(DBInstanceIdentifier='db-ztoth')
            print("[SUCCESS] RDS has been deleted.")
        except Exception as error:
            print(f"[ ERROR ] Error removing RDS: {error}")


print("--==--EndOfScript--==--")
