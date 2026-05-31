#include "dataexporter.h"
#include <QFile>
#include <QTextStream>
#include <QStringList>
#include <cmath>

DataExporter::DataExporter()
{
}

QString DataExporter::formatDouble(double value, int precision)
{
    if (std::isnan(value) || std::isinf(value)) {
        return "NaN";
    }
    return QString::number(value, 'g', precision);
}

bool DataExporter::exportToCSV(const QString& filename,
                              const std::vector<double>& time,
                              const std::vector<double>& x,
                              const std::vector<double>& y,
                              const std::vector<double>& z)
{
    QStringList headers = {"Time", "X", "Y", "Z"};
    std::vector<std::vector<double>> data;
    data.push_back(time);
    data.push_back(x);
    data.push_back(y);
    data.push_back(z);
    return exportToCSV(filename, data, headers);
}

bool DataExporter::exportToCSV(const QString& filename,
                              const std::vector<std::vector<double>>& data,
                              const QStringList& headers)
{
    if (data.empty()) return false;

    QFile file(filename);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) {
        return false;
    }

    QTextStream out(&file);
    out.setRealNumberPrecision(10);

    if (!headers.isEmpty()) {
        out << headers.join(",") << "\n";
    }

    size_t numRows = data[0].size();
    size_t numCols = data.size();

    for (size_t row = 0; row < numRows; ++row) {
        QStringList line;
        for (size_t col = 0; col < numCols; ++col) {
            if (row < data[col].size()) {
                line.append(formatDouble(data[col][row]));
            } else {
                line.append("");
            }
        }
        out << line.join(",") << "\n";
    }

    file.close();
    return true;
}
