import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, User, ReferenceGenome, GeneAnnotation
from werkzeug.security import generate_password_hash

app = create_app()

MAIZE_INBRED_LINES = [
    {
        "name": "B73",
        "version": "v5",
        "species": "Zea mays",
        "description": "玉米自交系B73是国际公认的玉米遗传学和基因组学研究的标准材料，是第一个完成全基因组测序的玉米自交系。",
        "chromosome_count": 10,
        "genome_size": "2.1 Gb",
        "annotation_version": "Zm-B73-REFERENCE-NAM-5.0",
    },
    {
        "name": "Mo17",
        "version": "v1",
        "species": "Zea mays",
        "description": "Mo17是另一个重要的玉米自交系，与B73一起广泛用于玉米遗传改良和杂种优势研究。",
        "chromosome_count": 10,
        "genome_size": "2.2 Gb",
        "annotation_version": "Zm-Mo17-REFERENCE-CAU-1.0",
    },
    {
        "name": "W22",
        "version": "v2",
        "species": "Zea mays",
        "description": "W22是经典的玉米遗传研究材料，常用于转座子诱变和基因功能研究。",
        "chromosome_count": 10,
        "genome_size": "2.1 Gb",
        "annotation_version": "Zm-W22-REFERENCE-NRGENE-2.0",
    },
    {
        "name": "PH207",
        "version": "v1",
        "species": "Zea mays",
        "description": "PH207是美国先锋公司培育的重要自交系，是现代玉米杂交种的重要亲本之一。",
        "chromosome_count": 10,
        "genome_size": "2.1 Gb",
        "annotation_version": "Zm-PH207-REFERENCE_NS-1.0",
    },
    {
        "name": "B97",
        "version": "v1",
        "species": "Zea mays",
        "description": "B97是NAM（Nested Association Mapping）群体的亲本之一，具有优良的农艺性状。",
        "chromosome_count": 10,
        "genome_size": "2.1 Gb",
        "annotation_version": "Zm-B97-REFERENCE_NAM-1.0",
    },
]

DEMO_USER = {
    "email": "demo@gwas.com",
    "password": "demo123456",
    "name": "演示用户",
}


def init_database():
    print("=" * 60)
    print("GWAS分析系统 - 数据库初始化")
    print("=" * 60)
    print()

    with app.app_context():
        print("1. 创建数据库表...")
        db.create_all()
        print("   ✓ 数据库表创建完成")
        print()

        print("2. 初始化演示用户...")
        existing_user = User.query.filter_by(email=DEMO_USER["email"]).first()
        if not existing_user:
            user = User(
                email=DEMO_USER["email"],
                password_hash=generate_password_hash(DEMO_USER["password"]),
                name=DEMO_USER["name"],
                created_at=datetime.utcnow(),
            )
            db.session.add(user)
            db.session.commit()
            print(f"   ✓ 演示用户创建成功: {DEMO_USER['email']} / {DEMO_USER['password']}")
        else:
            print(f"   ℹ 演示用户已存在: {DEMO_USER['email']}")
        print()

        print("3. 初始化参考基因组数据...")
        for line_data in MAIZE_INBRED_LINES:
            genome_id = f"{line_data['name']}_{line_data['version']}"
            existing_genome = ReferenceGenome.query.filter_by(id=genome_id).first()
            if not existing_genome:
                genome = ReferenceGenome(
                    id=genome_id,
                    name=line_data["name"],
                    species=line_data["species"],
                    version=line_data["version"],
                    description=line_data["description"],
                    created_at=datetime.utcnow(),
                )
                db.session.add(genome)
                print(f"   ✓ 添加参考基因组: {line_data['name']} {line_data['version']}")
            else:
                print(f"   ℹ 参考基因组已存在: {line_data['name']} {line_data['version']}")

        db.session.commit()
        print()

        print("4. 初始化基因注释数据（示例）...")
        example_genes = [
            {
                "gene_id": "Zm00001eb001010",
                "gene_name": "tb1",
                "chromosome": "1",
                "start_pos": 256000000,
                "end_pos": 256100000,
                "strand": "+",
                "description": "teosinte branched 1 - 控制玉米分枝数的关键基因",
            },
            {
                "gene_id": "Zm00001eb002020",
                "gene_name": "tga1",
                "chromosome": "4",
                "start_pos": 45000000,
                "end_pos": 45100000,
                "strand": "-",
                "description": "teosinte glume architecture 1 - 控制玉米籽粒包裹的关键基因",
            },
            {
                "gene_id": "Zm00001eb003030",
                "gene_name": "vgt1",
                "chromosome": "8",
                "start_pos": 125000000,
                "end_pos": 125100000,
                "strand": "+",
                "description": "vegetative to generative transition 1 - 控制玉米开花期的关键基因",
            },
        ]

        for gene_data in example_genes:
            existing_gene = GeneAnnotation.query.filter_by(
                gene_id=gene_data["gene_id"]
            ).first()
            if not existing_gene:
                gene = GeneAnnotation(
                    **gene_data,
                    reference_genome_id="B73_v5",
                    created_at=datetime.utcnow(),
                )
                db.session.add(gene)
                print(f"   ✓ 添加基因注释: {gene_data['gene_name']} ({gene_data['gene_id']})")

        db.session.commit()
        print()

        print("=" * 60)
        print("✓ 数据库初始化完成！")
        print("=" * 60)
        print()
        print("演示账号:")
        print(f"  邮箱: {DEMO_USER['email']}")
        print(f"  密码: {DEMO_USER['password']}")
        print()
        print("参考基因组:")
        for line in MAIZE_INBRED_LINES:
            print(f"  - {line['name']} {line['version']}")
        print()


if __name__ == "__main__":
    init_database()
