import enum

from sqlalchemy import (
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    DateTime,
    Date,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import sqlalchemy as sa
from sqlalchemy.schema import Index

from billparser.db.caching import CacheableMixin, query_callable, regions

Base = declarative_base()


class CastingArray(ARRAY):
    def bind_expression(self, bindvalue):
        return sa.cast(bindvalue, self)


class LegislationType(enum.Enum):
    Bill = "Bill"
    CRes = "Continuing Resolution"
    Res = "Resolution"
    JRes = "Joint Resolution"


class LegislationChamber(enum.Enum):
    House = "House"
    Senate = "Senate"


# https://www.senate.gov/legislative/KeytoVersionsofPrintedLegislation.htm
class LegislationVersionEnum(enum.Enum):
    IS = "IS"  # Introduced in the Senate
    IH = "IH"  # Introduced in the House
    RAS = "RAS"  # Referred with Amendments Senate
    RAH = "RAH"  # Referred with Amendments House
    RFS = "RFS"  # Referred in Senate
    RFH = "RFH"  # Referred in House
    RDS = "RDS"  # Received in Senate
    RHS = "RHS"  # Received in House
    RCS = "RCS"  # Reference Change Senate
    RCH = "RCH"  # Reference Change House
    RS = "RS"  # Reported in the Senate
    RH = "RH"  # Reported in the House
    PCS = "PCS"  # Placed on Calendar Senate
    PCH = "PCH"  # Placed on Calendar House
    CPS = "CPS"  # Considered and Passed Senate
    CPH = "CPH"  # Considered and Passed House
    EAS = "EAS"  # Engrossed amendment Senate
    EAH = "EAH"  # Engrossed amendment House
    ES = "ES"  # Engrossed in the Senate
    EH = "EH"  # Engrossed in the House
    ENR = "ENR"  # Enrolled


class Congress(Base):
    """
        Holds the relationships for the Congress sessions
    """

    __tablename__ = "congress"

    congress_id = Column(Integer, primary_key=True)
    session_number = Column(Integer)

    start_year = Column(Integer)
    end_year = Column(Integer)


class Version(Base):

    __tablename__ = "version"

    version_id = Column(Integer, primary_key=True)
    base_id = Column(
        Integer, ForeignKey("version.version_id", ondelete="CASCADE"), index=True
    )

    def to_dict(self):
        boi = {
            "version_id": self.version_id,
            "title": "Legacy Title",
            "base_id": self.base_id,
        }
        return {k: v for (k, v) in boi.items() if v is not None}


class Legislation(Base):
    """
    Represents a single piece of legislation, attached will be LegislationVersions
    This will be the one that holds the references to the sponsers/cosponsers
    """

    __tablename__ = "legislation"
    __table_args__ = (
        UniqueConstraint("chamber", "number", "legislation_type", name="unq_bill"),
    )
    legislation_id = Column(Integer, primary_key=True)

    chamber = Column(Enum(LegislationChamber), index=True)
    legislation_type = Column(Enum(LegislationType))

    number = Column(Integer)
    title = Column(String)

    congress_id = Column(
        Integer, ForeignKey("congress.congress_id", ondelete="CASCADE")
    )
    version_id = Column(Integer, ForeignKey("version.version_id", ondelete="CASCADE"))
    versions = versions = relationship("LegislationVersion")

    def to_dict(self):
        boi = {
            "bill_id": str(self.legislation_id),
            "chamber": self.chamber.value,
            "bill_type": "BillTypes." + self.legislation_type.value,
            "bill_number": str(self.number),
            "bill_title": self.title,
        }
        return {k: v for (k, v) in boi.items() if v is not None}


class LegislationVersion(Base):
    """
    Represents a single version of legislation, as described at one of the 11 possible version types
    """

    __tablename__ = "legislation_version"

    legislation_version_id = Column(Integer, primary_key=True)

    legislation_version = Column(Enum(LegislationVersionEnum), index=True)

    effective_date = Column(Date)

    legislation_id = Column(
        Integer,
        ForeignKey("legislation.legislation_id", ondelete="CASCADE"),
        index=True,
    )
    version_id = Column(
        Integer, ForeignKey("version.version_id", ondelete="CASCADE"), index=True
    )

    created_at = Column(DateTime(timezone=False), server_default=func.now())
    completed_at = Column(DateTime)

    def to_dict(self):
        boi = {
            "bill_version_id": str(self.legislation_version_id),
            "bill_id": str(self.legislation_id),
            "bill_version": self.legislation_version.value.lower(),
        }
        return {k: v for (k, v) in boi.items() if v is not None}


try:
    Index(
        "legis_version",
        LegislationVersion.legislation_version,
        LegislationVersion.legislation_id,
    )
except:
    pass


class LegislationContent(Base):
    __tablename__ = "legislation_content"

    legislation_content_id = Column(Integer, primary_key=True)

    parent_id = Column(
        Integer, ForeignKey("legislation_content.legislation_content_id")
    )

    lc_ident = Column(String)  # Will be used to identify differences between versions

    order_number = Column(Integer, default=0)

    section_display = Column(String)
    heading = Column(String)
    content_str = Column(String)
    content_type = Column(String)

    action_parse = Column(CastingArray(JSONB))

    legislation_version_id = Column(
        Integer,
        ForeignKey("legislation_version.legislation_version_id", ondelete="CASCADE"),
        index=True,
    )

    # TODO: Fix these to use new names
    def to_dict(self):
        ap = {}
        for obj in self.action_parse:
            keys = [x for x in obj.keys() if x not in ["changed", "parsed_cite"]]
            ap[keys[0]] = obj.get("changed", False)

        boi = {
            "bill_content_id": self.legislation_content_id,
            "content_type": self.content_type,
            "order": self.order_number,
            "parent": self.parent_id,
            # "number": self.number,
            "display": self.section_display,
            "heading": self.heading,
            "content": self.content_str,
            "version": str(self.legislation_version_id),
            "ap": ap,
        }
        return {k: v for (k, v) in boi.items() if v is not None and v != {}}


class USCRelease(Base):
    """
    Represents a release point of the USCode, as described by the prior release points page
    """

    __tablename__ = "usc_release"

    usc_release_id = Column(Integer, primary_key=True)

    short_title = Column(String)
    effective_date = Column(Date)
    long_title = Column(String)

    created_at = Column(DateTime(timezone=False), server_default=func.now())
    version_id = Column(Integer, ForeignKey("version.version_id", ondelete="CASCADE"))

    def to_dict(self):

        boi = {"usc_release_id": self.usc_release_id, "version_id": self.version_id}
        return {k: v for (k, v) in boi.items() if v is not None and v != {}}


class USCChapter(Base):
    """
    A single chapter in the USC for a given release point
    """

    __tablename__ = "usc_chapter"

    usc_chapter_id = Column(Integer, primary_key=True)

    short_title = Column(String)
    long_title = Column(String)

    document = Column(String)

    usc_ident = Column(String)

    created_at = Column(DateTime(timezone=False), server_default=func.now())

    usc_release_id = Column(
        Integer, ForeignKey("usc_release.usc_release_id", ondelete="CASCADE")
    )
    version_id = Column(
        Integer, ForeignKey("version.version_id", ondelete="CASCADE"), index=True
    )

    def to_dict(self):
        boi = {
            "chapter_id": self.usc_chapter_id,
            "ident": self.usc_ident,
            "number": self.short_title,
            "name": self.long_title,
            "version": self.version_id,
        }
        return {k: v for (k, v) in boi.items() if v is not None}


class USCSection(Base):
    """
    A section of a chapter in the usc code
    """

    __tablename__ = "usc_section"

    usc_section_id = Column(Integer, primary_key=True)

    usc_ident = Column(String)
    usc_guid = Column(String)  # Might be a useless column

    number = Column(String)
    section_display = Column(String)
    heading = Column(String)

    usc_chapter_id = Column(
        Integer,
        ForeignKey("usc_chapter.usc_chapter_id", ondelete="CASCADE"),
        index=True,
    )
    version_id = Column(
        Integer, ForeignKey("version.version_id", ondelete="CASCADE"), index=True
    )

    def to_dict(self):
        boi = {
            "section_id": self.usc_section_id,
            "ident": self.usc_ident,
            "number": self.number,
            "display": self.section_display,
            "heading": self.heading,
            "chapter_id": self.usc_chapter_id,
            "version": self.version_id,
        }
        return {k: v for (k, v) in boi.items() if v is not None}


class USCContent(Base):
    """
    A content of a chapter in the usc code
    """

    __tablename__ = "usc_content"

    usc_content_id = Column(Integer, primary_key=True)

    parent_id = Column(Integer, ForeignKey("usc_content.usc_content_id"), index=True)

    usc_ident = Column(String)
    usc_guid = Column(String)  # Might be a useless column

    order_number = Column(Integer, default=0)

    number = Column(String)
    section_display = Column(String)
    heading = Column(String)
    content_str = Column(String)
    content_type = Column(String)

    usc_section_id = Column(
        Integer,
        ForeignKey("usc_section.usc_section_id", ondelete="CASCADE"),
        index=True,
    )
    version_id = Column(
        Integer, ForeignKey("version.version_id", ondelete="CASCADE"), index=True
    )

    def to_dict(self):
        boi = {
            "content_id": self.usc_content_id,
            "content_type": self.content_type,
            "section_id": self.usc_section_id,
            "order": self.order_number,
            "parent": self.parent_id,
            "ident": self.usc_ident,
            "number": self.number,
            "display": self.section_display,
            "heading": self.heading,
            "content": self.content_str,
            "version": self.version_id,
        }
        return {k: v for (k, v) in boi.items() if v is not None}


try:
    Index("content_ident", USCContent.usc_ident, USCContent.version_id)
except:
    pass


class USCContentDiff(Base):
    """
    A contentdiff of a specific content
    """

    __tablename__ = "usc_content_diff"

    usc_content_diff_id = Column(Integer, primary_key=True)

    usc_ident = Column(String)
    usc_guid = Column(String)  # Might be a useless column

    order_number = Column(Integer)
    number = Column(String)
    section_display = Column(String)
    heading = Column(String)
    content_str = Column(String)
    content_type = Column(String)

    usc_content_id = Column(
        Integer, ForeignKey("usc_content.usc_content_id"), index=True
    )

    usc_section_id = Column(
        Integer,
        ForeignKey("usc_section.usc_section_id", ondelete="CASCADE"),
        index=True,
    )
    usc_chapter_id = Column(
        Integer,
        ForeignKey("usc_chapter.usc_chapter_id", ondelete="CASCADE"),
        index=True,
    )
    legislation_content_id = Column(
        Integer,
        ForeignKey("legislation_content.legislation_content_id", ondelete="CASCADE"),
        index=True,
    )
    version_id = Column(
        Integer, ForeignKey("version.version_id", ondelete="CASCADE"), index=True
    )

    def to_dict(self):

        boi = {
            "id": self.usc_content_diff_id,
            "content_id": self.usc_content_id,
            "section_id": self.usc_section_id,
            "chapter_id": self.usc_chapter_id,
            "order": self.order_number,
            "number": self.number,
            "display": self.section_display,
            "heading": self.heading,
            "content": self.content_str,
            "version": self.version_id,
        }
        return {k: v for (k, v) in boi.items() if v is not None}
