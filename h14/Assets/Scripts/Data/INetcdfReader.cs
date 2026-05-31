using System.Threading.Tasks;
using FlowVisualization.Core;

namespace FlowVisualization.Data
{
    public interface INetcdfReader
    {
        Task<TimeVaryingField> LoadAsync(string filePath);
        TimeVaryingField Load(string filePath);
    }

    public enum NetCDFDataType
    {
        Float,
        Double,
        Int,
        Short,
        Byte
    }

    public class NetCDFVariableInfo
    {
        public string Name;
        public int[] Dimensions;
        public NetCDFDataType DataType;
        public float[] MinValues;
        public float[] MaxValues;
    }
}
