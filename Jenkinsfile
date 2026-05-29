pipeline {
    agent any

    stages {

        // Pull code from GitHub
        stage('Checkout Code') {
            steps {
                echo 'Fetching latest code...'
                checkout scm
            }
        }

        // Deploy to AWS EC2
        stage('Deploy to EC2') {
            steps {
                echo 'Deploying application to EC2...'

                withCredentials([
                    sshUserPrivateKey(
                        credentialsId: 'ec2-ssh-key',
                        keyFileVariable: 'SSH_KEY'
                    )
                ]) {

                    // Copy deploy script
                    sh '''
                    scp -i $SSH_KEY -o StrictHostKeyChecking=no \
                    deploy.sh ec2-user@13.233.252.35:/home/ec2-user/
                    '''

                    // Run deploy script on EC2
                    sh '''
                    ssh -i $SSH_KEY -o StrictHostKeyChecking=no \
                    ec2-user@13.233.252.35 \
                    "chmod +x /home/ec2-user/deploy.sh && /home/ec2-user/deploy.sh"
                    '''
                }
            }
        }
    }

    post {
        success {
            echo 'Deployment Successful!'
        }

        failure {
            echo 'Deployment Failed!'
        }
    }
}