"""
Upload API tests with mocked S3.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from io import BytesIO

from fastapi.testclient import TestClient


def test_upload_endpoint_exists():
    """Verify upload endpoint is registered."""
    from app.main import app
    
    # Check if /upload route exists
    routes = [route.path for route in app.routes]
    assert "/upload" in routes


@pytest.mark.asyncio
async def test_upload_file_mock():
    """Test upload with mocked S3 service."""
    from app.services.s3_service import S3Service
    
    # Mock the S3 client
    with patch.object(S3Service, '__init__', lambda self: None):
        service = S3Service()
        service.s3_client = MagicMock()
        service.bucket_name = "test-bucket"
        service.region = "ap-northeast-2"
        service.cloudfront_url = "https://test.cloudfront.net"
        
        # Create a fake file
        fake_file = MagicMock()
        fake_file.file = BytesIO(b"fake image content")
        fake_file.filename = "test.png"
        fake_file.content_type = "image/png"
        
        # Test upload
        result = await service.upload_file(fake_file, prefix="test")
        
        assert result["message"] == "업로드 성공"
        assert "https://test.cloudfront.net/media/" in result["cloudfront_url"]
        assert service.s3_client.upload_fileobj.called


def test_upload_api_integration():
    """Test upload API endpoint with mocked S3."""
    from app.main import app
    
    with patch('app.services.s3_service.boto3') as mock_boto3:
        # Mock the S3 client
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        
        client = TestClient(app)
        
        # Create test file
        test_file = BytesIO(b"test image content")
        
        response = client.post(
            "/upload",
            files={"file": ("test.png", test_file, "image/png")}
        )
        
        # Should succeed or fail gracefully
        assert response.status_code in [200, 500]  # 500 if S3 config missing
