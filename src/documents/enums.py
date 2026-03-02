import enum


class SourceType(str, enum.Enum):
    """File format of the original document before ingestion."""

    PDF = "pdf"
    ODT = "odt"
    HTML = "html"
    DOCX = "docx"
    TXT = "txt"


class Jurisdiction(str, enum.Enum):
    """Regulatory body / jurisdiction that issued the document."""

    EASA = "easa"
    FAA = "faa"
    ICAO = "icao"
    NATIONAL = "national"  # state-level authority (specify in metadata)


class DocType(str, enum.Enum):
    """Functional category of the document."""

    REGULATION = "regulation"  # binding legal text (e.g. EU reg 965/2012)
    IMPLEMENTING_RULE = "implementing_rule"  # IRs, AMC, GM issued under a regulation
    MANUAL = "manual"  # operations manuals, airline manuals
    GUIDANCE = "guidance"  # advisory circulars, safety information bulletins
    AIP = "aip"  # aeronautical information publication
    CIRCULAR = "circular"  # information circulars, NOTAMs (long-lived)


class Language(str, enum.Enum):
    """Supported document languages."""

    EN = "eng"
    RU = "rus"


class IngestionStatus(str, enum.Enum):
    """Lifecycle state of an ingestion run."""

    STARTED = "started"
    SUCCESS = "success"
    FAILED = "failed"
