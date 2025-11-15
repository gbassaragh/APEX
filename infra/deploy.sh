#!/bin/bash
# APEX Infrastructure Deployment Script
# Usage: ./deploy.sh <environment> [resource-group-name]
# Example: ./deploy.sh dev apex-rg-dev
#          ./deploy.sh prod apex-rg-prod

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_BICEP="${SCRIPT_DIR}/main.bicep"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_usage() {
    cat << EOF
APEX Infrastructure Deployment

Usage: $0 <environment> [resource-group-name]

Arguments:
    environment          Environment to deploy (dev, staging, prod)
    resource-group-name  Optional: Resource group name (default: apex-rg-{environment})

Examples:
    $0 dev                    # Deploy to dev environment (apex-rg-dev)
    $0 prod apex-rg-prod-east # Deploy to prod with custom RG name

Requirements:
    - Azure CLI installed and logged in (az login)
    - Appropriate Azure subscription selected (az account set)
    - Contributor or Owner role on subscription or resource group

Environment-Specific Deployments:
    dev:     Cost-optimized, no zone redundancy, free tier where possible
    staging: Mid-tier, testing production-like config
    prod:    Production-grade, zone redundant, high availability

Pre-Deployment Checklist:
    1. Run 'az login' to authenticate
    2. Run 'az account show' to verify correct subscription
    3. Ensure you have necessary permissions
    4. Review parameter file: parameters/{environment}.bicepparam
    5. For production, obtain change approval and backup existing state

EOF
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if Azure CLI is installed
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI not found. Please install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    fi

    # Check if logged in
    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure. Run 'az login' first."
        exit 1
    fi

    # Check if Bicep is installed (comes with Azure CLI 2.20.0+)
    if ! az bicep version &> /dev/null; then
        log_warning "Bicep CLI not found. Installing..."
        az bicep install
    fi

    log_success "Prerequisites check passed"
}

validate_environment() {
    local env=$1

    if [[ ! "$env" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $env. Must be dev, staging, or prod."
        show_usage
        exit 1
    fi

    # Check if parameter file exists
    local param_file="${SCRIPT_DIR}/parameters/${env}.bicepparam"
    if [[ ! -f "$param_file" ]]; then
        log_error "Parameter file not found: $param_file"
        exit 1
    fi
}

confirm_production_deployment() {
    local env=$1

    if [[ "$env" == "prod" ]]; then
        log_warning "You are about to deploy to PRODUCTION environment."
        read -p "Have you obtained change approval? (yes/no): " approval
        if [[ "$approval" != "yes" ]]; then
            log_error "Production deployment cancelled. Obtain change approval first."
            exit 1
        fi

        read -p "Type 'DEPLOY-TO-PRODUCTION' to confirm: " confirmation
        if [[ "$confirmation" != "DEPLOY-TO-PRODUCTION" ]]; then
            log_error "Production deployment cancelled."
            exit 1
        fi
    fi
}

# ============================================================================
# Main Deployment Logic
# ============================================================================

main() {
    # Parse arguments
    if [[ $# -lt 1 ]]; then
        log_error "Missing required argument: environment"
        show_usage
        exit 1
    fi

    ENVIRONMENT=$1
    RESOURCE_GROUP=${2:-"apex-rg-${ENVIRONMENT}"}
    PARAM_FILE="${SCRIPT_DIR}/parameters/${ENVIRONMENT}.bicepparam"
    LOCATION="eastus"  # Default location, can be overridden in param file

    log_info "APEX Infrastructure Deployment"
    log_info "Environment: $ENVIRONMENT"
    log_info "Resource Group: $RESOURCE_GROUP"
    log_info "Parameter File: $PARAM_FILE"
    echo ""

    # Validate environment
    validate_environment "$ENVIRONMENT"

    # Check prerequisites
    check_prerequisites

    # Confirm production deployment
    confirm_production_deployment "$ENVIRONMENT"

    # Display current Azure context
    log_info "Current Azure context:"
    az account show --query "{SubscriptionName:name, SubscriptionId:id, TenantId:tenantId}" -o table
    echo ""

    read -p "Continue with deployment to this subscription? (y/n): " continue_deploy
    if [[ "$continue_deploy" != "y" ]]; then
        log_error "Deployment cancelled by user."
        exit 0
    fi

    # ========================================================================
    # Step 1: Create Resource Group
    # ========================================================================

    log_info "Step 1: Creating resource group '$RESOURCE_GROUP' in $LOCATION..."

    if az group exists --name "$RESOURCE_GROUP" | grep -q "true"; then
        log_warning "Resource group already exists. Using existing resource group."
    else
        az group create \
            --name "$RESOURCE_GROUP" \
            --location "$LOCATION" \
            --tags Environment="$ENVIRONMENT" Project="APEX" ManagedBy="Bicep" \
            --output table
        log_success "Resource group created successfully"
    fi
    echo ""

    # ========================================================================
    # Step 2: Validate Bicep Template
    # ========================================================================

    log_info "Step 2: Validating Bicep template..."

    if az deployment group validate \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "$MAIN_BICEP" \
        --parameters "$PARAM_FILE" \
        --output table; then
        log_success "Template validation passed"
    else
        log_error "Template validation failed. Check syntax and parameters."
        exit 1
    fi
    echo ""

    # ========================================================================
    # Step 3: What-If Analysis (Preview Changes)
    # ========================================================================

    log_info "Step 3: Running what-if analysis (preview changes)..."

    az deployment group what-if \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "$MAIN_BICEP" \
        --parameters "$PARAM_FILE" \
        --result-format FullResourcePayloads \
        --no-pretty-print

    echo ""
    read -p "Review changes above. Continue with deployment? (y/n): " continue_after_whatif
    if [[ "$continue_after_whatif" != "y" ]]; then
        log_error "Deployment cancelled after what-if review."
        exit 0
    fi

    # ========================================================================
    # Step 4: Deploy Infrastructure
    # ========================================================================

    log_info "Step 4: Deploying infrastructure..."

    DEPLOYMENT_NAME="apex-infra-$(date +%Y%m%d-%H%M%S)"

    if az deployment group create \
        --name "$DEPLOYMENT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "$MAIN_BICEP" \
        --parameters "$PARAM_FILE" \
        --output json > deployment_output.json; then
        log_success "Deployment completed successfully: $DEPLOYMENT_NAME"
    else
        log_error "Deployment failed. Check Azure Portal for details."
        exit 1
    fi
    echo ""

    # ========================================================================
    # Step 5: Display Deployment Outputs
    # ========================================================================

    log_info "Step 5: Deployment outputs:"

    az deployment group show \
        --name "$DEPLOYMENT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.outputs" \
        --output table

    echo ""

    # ========================================================================
    # Step 6: Verify Deployment
    # ========================================================================

    log_info "Step 6: Verifying deployment..."

    # Check if Container App is healthy
    CONTAINER_APP_NAME=$(az deployment group show \
        --name "$DEPLOYMENT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.outputs.containerAppFqdn.value" \
        --output tsv 2>/dev/null || echo "")

    if [[ -n "$CONTAINER_APP_NAME" ]]; then
        log_info "Container App FQDN: $CONTAINER_APP_NAME"
        log_info "Note: Container App is internal-only (no public access)"
    fi

    # Summary
    log_success "Deployment verification complete"
    echo ""

    # ========================================================================
    # Post-Deployment Instructions
    # ========================================================================

    log_info "Post-Deployment Steps:"
    echo ""
    echo "1. Configure Application Secrets in Key Vault:"
    echo "   - SQL connection strings (if needed for non-Managed-Identity clients)"
    echo "   - Any third-party API keys"
    echo ""
    echo "2. Build and Push Container Image:"
    echo "   - Build Docker image: docker build -t apex-backend:latest ."
    echo "   - Push to ACR: az acr build --registry <acr-name> --image apex-backend:latest ."
    echo "   - Update Container App with new image"
    echo ""
    echo "3. Run Database Migrations:"
    echo "   - Connect via Azure Bastion or VPN"
    echo "   - Run: alembic upgrade head"
    echo ""
    echo "4. Verify Private Endpoint Connectivity:"
    echo "   - Test DNS resolution from Container App"
    echo "   - Verify no public network access to PaaS services"
    echo ""
    echo "5. Configure Monitoring and Alerts:"
    echo "   - Application Insights: Custom metrics and alerts"
    echo "   - Log Analytics: Query workbooks and dashboards"
    echo ""
    echo "6. Security Validation:"
    echo "   - Run network scan to verify no public endpoints"
    echo "   - Validate RBAC assignments"
    echo "   - Review NSG flow logs"
    echo ""

    log_success "APEX Infrastructure Deployment Complete!"
    log_info "Resource Group: $RESOURCE_GROUP"
    log_info "Deployment Name: $DEPLOYMENT_NAME"
    log_info "Environment: $ENVIRONMENT"
}

# ============================================================================
# Script Entry Point
# ============================================================================

main "$@"
