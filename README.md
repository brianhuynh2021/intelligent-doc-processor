# 🚀 Intelligent Document Processor

> AI-powered document processing platform with OCR, text extraction, and intelligent search capabilities using RAG (Retrieval-Augmented Generation).

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Project Overview

An intelligent document processing system that combines OCR, NLP, and Large Language Models to extract, analyze, and query information from various document formats (PDF, DOCX, images).

---

## ✨ Key Features (Planned)

### Phase 1 - Core Features (Month 1-2)
- 📄 **Multi-format Support**: PDF, DOCX, Excel, Images
- 🔍 **OCR Processing**: Tesseract-based text extraction
- 💬 **RAG Chat**: Ask questions about your documents
- 🔎 **Semantic Search**: Vector-based document retrieval
- 👤 **User Management**: Authentication & authorization

### Phase 2 - Advanced Features (Month 3-4)
- 📊 **Table Extraction**: Structured data from tables
- 🖼️ **Image Analysis**: Vision model integration
- 📝 **Form Processing**: Auto-fill & validation
- 🏷️ **Auto-Classification**: Document categorization
- 🔗 **Knowledge Graph**: Entity relationship extraction

### Phase 3 - Production Ready (Month 5-6)
- 🏢 **Multi-Tenancy**: Isolated environments
- 📈 **Analytics Dashboard**: Usage & performance metrics
- 🔌 **API Integrations**: Zapier, Slack, Google Drive
- 🌍 **Internationalization**: Multi-language support
- 🚀 **Production Deployment**: Kubernetes, monitoring

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Client Applications                │
│            (Web UI, Mobile, API Clients)             │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│                    API Gateway                       │
│              (FastAPI + JWT Auth)                    │
└─────────────────────────────────────────────────────┘
                          ↓
         ┌────────────────┼────────────────┐
         ↓                ↓                ↓
┌────────────────┐ ┌─────────────┐ ┌──────────────┐
│  Document      │ │   Search    │ │    Chat      │
│  Processing    │ │   Service   │ │   Service    │
│  (OCR, NLP)    │ │  (Vector)   │ │    (RAG)     │
└────────────────┘ └─────────────┘ └──────────────┘
         │                │                │
         └────────────────┼────────────────┘
                          ↓
         ┌────────────────┼────────────────┐
         ↓                ↓                ↓
┌────────────────┐ ┌─────────────┐ ┌──────────────┐
│   PostgreSQL   │ │   Qdrant    │ │    Redis     │
│   (Metadata)   │ │  (Vectors)  │ │   (Cache)    │
└────────────────┘ └─────────────┘ └──────────────┘
```

---

## 🛠️ Tech Stack

### Backend Framework
- **FastAPI** 0.104.1 - Modern async web framework
- **Pydantic** 2.5.0 - Data validation
- **SQLAlchemy** 2.0.23 - ORM
- **Alembic** 1.13.0 - Database migrations

### Databases
- **PostgreSQL** 15 - Relational database for metadata
- **Qdrant** - Vector database for semantic search
- **Redis** 7 - Caching & message broker

### AI/ML Stack
- **OpenAI API** - GPT-4 for chat & embeddings
- **LangChain** 0.0.340 - RAG framework
- **Tesseract** - OCR engine
- **spaCy** - NLP processing

### Document Processing
- **PyPDF2** 3.0.1 - PDF parsing
- **python-docx** 1.1.0 - Word documents
- **openpyxl** 3.1.2 - Excel files
- **Pillow** 10.1.0 - Image processing

### Infrastructure
- **Docker** + Docker Compose - Containerization
- **Celery** 5.3.4 - Async task processing
- **Nginx** - Reverse proxy (production)
- **Kubernetes** - Orchestration (production)

### Development Tools
- **pytest** 7.4.3 - Testing framework
- **black** 23.11.0 - Code formatting
- **ruff** 0.1.6 - Fast linter
- **mypy** 1.7.1 - Type checking
- **pre-commit** 3.5.0 - Git hooks

---

## 🚀 Quick Start

### Prerequisites

```bash
- Docker & Docker Compose
- Python 3.11+
- Git
```

### Installation

#### 1. Clone Repository
```bash
git clone https://github.com/yourusername/intelligent-doc-processor.git
cd intelligent-doc-processor
```

#### 2. Create Environment
```bash
# Create uploads directory
mkdir -p uploads

# Copy environment template (when ready)
cp .env.example .env
```

#### 3. Start Services
```bash
# Build and start all services
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### 4. Verify Installation
```bash
# Check service health
docker-compose ps

# Expected output:
# doc_processor_db       Up (healthy)
# doc_processor_redis    Up (healthy)
# doc_processor_api      Up (healthy)

# Test API
curl http://localhost:8000/health

# Open Swagger UI
open http://localhost:8000/docs
```
---

## 🔌 Services & Ports

| Service | Port | Internal Port | Description |
|---------|------|---------------|-------------|
| **FastAPI** | 8000 | 8000 | Main API server |
| **PostgreSQL** | 5433 | 5432 | Database (external port 5433 to avoid local conflict) |
| **Redis** | 6379 | 6379 | Cache & message broker |
| **Qdrant** | 6333 | 6333 | Vector database (coming) |

### Access URLs
- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **API Info**: http://localhost:8000/api/v1/info

---
### Database Migrations

```bash
# Generate new migration
docker-compose exec api alembic revision --autogenerate -m "Description"

# Apply migrations
docker-compose exec api alembic upgrade head

# Rollback one migration
docker-compose exec api alembic downgrade -1

# View migration history
docker-compose exec api alembic history

# Check current revision
docker-compose exec api alembic current
```

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Format code
black app/
isort app/

# Lint
ruff check app/
flake8 app/

# Type check
mypy app/

# All checks
pre-commit run --all-files
```

### Database Access

```bash
# Connect to PostgreSQL
docker-compose exec db psql -U postgres -d doc_processor

# Common psql commands:
\dt              # List tables
\d users         # Describe users table
\du              # List users
\l               # List databases
\q               # Quit
```

### Redis Access

```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Common Redis commands:
PING             # Test connection
KEYS *           # List all keys
GET key          # Get value
FLUSHALL         # Clear all (careful!)
```

---

## 🧪 Testing Strategy

### Test Pyramid
```
        /\
       /  \      E2E Tests (10%)
      /────\     Integration Tests (30%)
     /──────\    Unit Tests (60%)
    /────────\
```

### Current Coverage
- **Unit Tests**: Coming in Week 3
- **Integration Tests**: Coming in Week 3
- **E2E Tests**: Coming in Week 4
- **Load Tests**: Coming in Week 4

**Target**: >85% code coverage

---

## 🤝 Contributing

This is a personal portfolio project, but feedback and suggestions are welcome!

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Development Guidelines
- Follow PEP 8 style guide
- Write tests for new features
- Update documentation
- Use conventional commits
- Ensure CI passes

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Brian Huynh**
- Portfolio: [your-portfolio.com]
- LinkedIn: [linkedin.com/in/yourprofile]
- GitHub: [@yourusername]
- Email: huynh2102@gmail.com

---

## 🙏 Acknowledgments

- FastAPI team for the amazing framework
- LangChain community for RAG patterns
- OpenAI for GPT-4 API
- PostgreSQL & Redis teams
- Docker & Kubernetes communities

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/intelligent-doc-processor/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/intelligent-doc-processor/discussions)
- **Email**: your.email@example.com

---

## 🔗 Links

- **Documentation**: [docs/](docs/)
- **API Docs**: http://localhost:8000/docs
- **ROADMAP**: [ROADMAP.md](ROADMAP.md)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md) (coming)

---

**Status**: 🟢 Active Development
**Last Updated**: Day 2 - October 2025
**Next Milestone**: Complete Day 2 migrations, start Day 3 authentication

---

Made with ❤️ and ☕ for FAANG interview preparation 🚀
