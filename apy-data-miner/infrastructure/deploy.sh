#!/bin/bash
set -e

#---------------------------------------------------------
# APY Data Miner - Deployment Script
#---------------------------------------------------------

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  APY Data Miner - AWS Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"

    if ! command -v aws &> /dev/null; then
        echo -e "${RED}Error: AWS CLI is not installed${NC}"
        echo "Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        exit 1
    fi

    if ! command -v sam &> /dev/null; then
        echo -e "${RED}Error: AWS SAM CLI is not installed${NC}"
        echo "Install: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
        exit 1
    fi

    if ! command -v node &> /dev/null; then
        echo -e "${RED}Error: Node.js is not installed${NC}"
        exit 1
    fi

    echo -e "${GREEN}All prerequisites met!${NC}"
    echo ""
}

# Get deployment parameters
get_parameters() {
    echo -e "${YELLOW}Configuration${NC}"
    echo ""

    # Environment
    read -p "Environment [dev/prod] (default: dev): " ENV
    ENV=${ENV:-dev}

    # Alchemy API Key
    read -p "Alchemy API Key: " ALCHEMY_KEY
    if [ -z "$ALCHEMY_KEY" ]; then
        echo -e "${RED}Error: Alchemy API Key is required${NC}"
        exit 1
    fi

    # Database password
    read -s -p "Database Password (min 8 chars): " DB_PASSWORD
    echo ""
    if [ ${#DB_PASSWORD} -lt 8 ]; then
        echo -e "${RED}Error: Password must be at least 8 characters${NC}"
        exit 1
    fi

    # AWS Region
    read -p "AWS Region (default: us-east-1): " AWS_REGION
    AWS_REGION=${AWS_REGION:-us-east-1}

    # Stack name
    STACK_NAME="apy-data-miner-${ENV}"

    echo ""
    echo -e "${GREEN}Configuration Summary:${NC}"
    echo "  Environment: $ENV"
    echo "  Region: $AWS_REGION"
    echo "  Stack Name: $STACK_NAME"
    echo ""
}

# Build Lambda packages
build_lambdas() {
    echo -e "${YELLOW}Building Lambda packages...${NC}"

    # Navigate to collector directory
    cd "$(dirname "$0")/../lambda/collector"

    # Install dependencies
    echo "Installing collector dependencies..."
    npm install --production

    cd "$(dirname "$0")"
    echo -e "${GREEN}Build complete!${NC}"
    echo ""
}

# Deploy with SAM
deploy_stack() {
    echo -e "${YELLOW}Deploying to AWS...${NC}"
    echo ""

    cd "$(dirname "$0")"

    # SAM build
    echo "Running SAM build..."
    sam build --template-file template.yaml

    # SAM deploy
    echo "Running SAM deploy..."
    sam deploy \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" \
        --parameter-overrides \
            Environment="$ENV" \
            AlchemyApiKey="$ALCHEMY_KEY" \
            DBPassword="$DB_PASSWORD" \
        --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
        --confirm-changeset \
        --no-fail-on-empty-changeset

    echo ""
    echo -e "${GREEN}Deployment complete!${NC}"
}

# Initialize database schema
init_database() {
    echo -e "${YELLOW}Do you want to initialize the database schema? [y/N]${NC}"
    read -p "" INIT_DB

    if [[ "$INIT_DB" =~ ^[Yy]$ ]]; then
        echo "Getting database endpoint..."

        DB_ENDPOINT=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --region "$AWS_REGION" \
            --query "Stacks[0].Outputs[?OutputKey=='DatabaseEndpoint'].OutputValue" \
            --output text)

        echo "Database endpoint: $DB_ENDPOINT"
        echo ""
        echo -e "${YELLOW}To initialize the schema, connect to the database:${NC}"
        echo ""
        echo "  psql -h $DB_ENDPOINT -U apyminer -d apyminer -f schema.sql"
        echo ""
        echo "Or use a bastion host / VPN since RDS is in private subnet."
    fi
}

# Print outputs
print_outputs() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Deployment Outputs${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""

    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" \
        --query "Stacks[0].Outputs" \
        --output table

    echo ""
    echo -e "${GREEN}Next Steps:${NC}"
    echo "1. Initialize database schema (run schema.sql)"
    echo "2. Test Lambda manually: aws lambda invoke --function-name apy-data-miner-collector-${ENV} out.json"
    echo "3. Monitor in CloudWatch: /aws/lambda/apy-data-miner-collector-${ENV}"
    echo ""
}

# Main execution
main() {
    check_prerequisites
    get_parameters
    build_lambdas
    deploy_stack
    init_database
    print_outputs
}

main "$@"
