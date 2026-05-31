#include <QApplication>
#include <QSurfaceFormat>
#include "mainwindow.h"

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);

    QSurfaceFormat format;
    format.setDepthBufferSize(24);
    format.setStencilBufferSize(8);
    format.setVersion(3, 3);
    format.setProfile(QSurfaceFormat::CompatibilityProfile);
    format.setSamples(4);
    QSurfaceFormat::setDefaultFormat(format);

    app.setApplicationName("Chaos Analyzer");
    app.setOrganizationName("Chaos Research");
    app.setApplicationVersion("1.0");

    MainWindow w;
    w.show();

    return app.exec();
}
