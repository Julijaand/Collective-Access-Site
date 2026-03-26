# Collective Access — Basics

## What is Collective Access?

Collective Access is a free, open-source collections management application for museums, archives, historical societies, and private collectors. It allows institutions to catalog, manage, and publish their collections online.

## Key Features

- Flexible data model — configurable to any collection type (art, archives, natural history, etc.)
- Powerful search and browse interface
- Media management — attach images, video, audio, and documents to records
- Relationships — link objects, entities, places, occurrences, and collections
- Import/export — supports CSV, XML, EAD, Dublin Core, and more
- Public access interface — publish your collection online
- Multi-language support
- Role-based access control — administrators, cataloguers, editors, read-only users

## Core Record Types

- **Objects** — physical or digital items in the collection (paintings, photographs, documents, etc.)
- **Entities** — people and organizations related to objects (artists, donors, manufacturers)
- **Places** — geographic locations
- **Occurrences** — events, exhibitions, loans
- **Collections** — groupings of objects
- **Lots** — acquisition lots (groups of objects acquired together)

## How to Access Your Instance

After subscribing to our SaaS platform, your Collective Access instance is available at your unique subdomain: `https://tenant-XXXXXXXX.yoursaas.com`

Default administrator login is created during the installation wizard. If you did not complete the wizard, navigate to `https://tenant-XXXXXXXX.yoursaas.com/install/index.php`.

## Logging In

1. Navigate to your instance URL
2. Click **Login** in the top right
3. Enter your administrator username and password
4. You will be taken to the back-end cataloguing interface

## User Roles

| Role | Access |
|------|--------|
| Administrator | Full access — settings, users, data model, all records |
| Editor | Create, edit, and delete records |
| Cataloguer | Create and edit records, no delete |
| Viewer | Read-only access |
| Public | Access only to published records via public interface |

## Configuring the Data Model

The data model (what fields and screens appear) is configured via **Manage → Administration → Configuration**. You can add custom fields (metadata elements), create display templates, and configure relationships between record types.
