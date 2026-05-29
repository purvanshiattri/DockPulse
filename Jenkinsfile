pipeline {
    agent any

    options {
        // Prevent concurrent builds on the same agent workspace to avoid conflicts
        disableConcurrentBuilds()
        // Print build timestamps in the console logs for easier debugging
        timestamps()
    }

    stages {
        // STAGE 1: Pull the latest source code from the Git repository (GitHub)
        stage('1. Checkout Code') {
            steps {
                echo 'Checking out revision from source repository...'
                checkout scm
            }
        }

        // STAGE 2: Deploy to AWS EC2 via SSH
        // --------------------------------------------------------------------------
        // DEPLOYMENT TO AWS EC2:
        // 1. Secure Authentication: Uses the Jenkins sshagent plugin and the 
        //    'ec2-ssh-key' credential containing the new-kehy.pem private key.
        // 2. Transfer Script: Copies deploy.sh to the home directory of the EC2 instance.
        // 3. Execution: Grants execution permission and runs deploy.sh to update the 
        //    Docker Compose services on the EC2 host.
        // --------------------------------------------------------------------------
        stage('2. Deploy to AWS EC2') {
            steps {
                echo 'Connecting to AWS EC2 instance and starting deployment...'
                withCredentials([sshUserPrivateKey(credentialsId: 'ec2-ssh-key', keyFileVariable: 'SSH_KEY')]) {
                    // Transfer the deployment script to EC2
                    sh 'scp -i $SSH_KEY -o StrictHostKeyChecking=no deploy.sh ec2-user@13.233.252.35:/home/ec2-user/deploy.sh'
                    // Execute the script on EC2
                    sh 'ssh -i $SSH_KEY -o StrictHostKeyChecking=no ec2-user@13.233.252.35 "chmod +x /home/ec2-user/deploy.sh && /home/ec2-user/deploy.sh"'
                }
            }
        }
    }

    post {
        success {
            echo '========================================================================'
            echo '  CI/CD PIPELINE EXECUTION SUCCEEDED: DEPLOYED TO AWS EC2 SUCCESSFULLY  '
            echo '========================================================================'
        }
        failure {
            echo '========================================================================'
            echo '  CI/CD PIPELINE EXECUTION FAILED: CHECK CONSOLE OUTPUT FOR FAILURE LOG '
            echo '========================================================================'
        }
    }
}