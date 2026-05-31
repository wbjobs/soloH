#ifndef DATAEXPORTER_H
#define DATAEXPORTER_H

#include <QString>
#include <vector>

class DataExporter {
public:
    DataExporter();

    static bool exportToCSV(const QString& filename,
                           const std::vector<double>& time,
                           const std::vector<double>& x,
                           const std::vector<double>& y,
                           const std::vector<double>& z);

    static bool exportToCSV(const QString& filename,
                           const std::vector<std::vector<double>>& data,
                           const QStringList& headers);

    static QString formatDouble(double value, int precision = 10);
};

#endif
