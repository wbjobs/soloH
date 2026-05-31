import { Scene } from '@babylonjs/core/scene';
import { Mesh } from '@babylonjs/core/Meshes/mesh';
import { GLTF2Export } from '@babylonjs/serializers/glTF';

export class GLTFExporter {
  static async exportPlant(
    scene: Scene,
    filename: string,
    _plantContainer?: Mesh
  ): Promise<void> {
    const exportOptions = {
      shouldExportNode: (node: any) => {
        if (node.name === 'ground' || node.name === 'camera' || 
            node.name.includes('Light')) {
          return false;
        }
        return true;
      }
    };
    
    try {
      const result = await GLTF2Export.GLBAsync(scene, filename, exportOptions);
      
      const glbBlob = (result as any).glb as Blob;
      
      const downloadLink = document.createElement('a');
      downloadLink.href = URL.createObjectURL(glbBlob);
      downloadLink.download = `${filename}.glb`;
      document.body.appendChild(downloadLink);
      downloadLink.click();
      document.body.removeChild(downloadLink);
      URL.revokeObjectURL(downloadLink.href);
      
      console.log(`Exported ${filename}.glb successfully`);
    } catch (error) {
      console.error('Error exporting glTF:', error);
      throw error;
    }
  }

  static async exportGLTF(
    scene: Scene,
    filename: string
  ): Promise<void> {
    const exportOptions = {
      shouldExportNode: (node: any) => {
        if (node.name === 'ground' || node.name === 'camera' || 
            node.name.includes('Light')) {
          return false;
        }
        return true;
      }
    };
    
    try {
      const result = await GLTF2Export.GLTFAsync(scene, filename, exportOptions);
      
      const resultObj = result as unknown as Record<string, Blob>;
      for (const key of Object.keys(resultObj)) {
        const blob = resultObj[key];
        const downloadLink = document.createElement('a');
        downloadLink.href = URL.createObjectURL(blob);
        downloadLink.download = key;
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
        URL.revokeObjectURL(downloadLink.href);
      }
      
      console.log(`Exported ${filename}.gltf successfully`);
    } catch (error) {
      console.error('Error exporting glTF:', error);
      throw error;
    }
  }
}
