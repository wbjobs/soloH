using System.Collections.Generic;
using UnityEngine;
using FlowVisualization.Core;

namespace FlowVisualization.Particles
{
    public class ParticlePool
    {
        private readonly Stack<Particle> _availableParticles;
        private readonly HashSet<Particle> _activeParticles;
        private readonly int _initialCapacity;
        private readonly int _maxCapacity;
        private readonly int _trailLength;

        public int ActiveCount => _activeParticles.Count;
        public int AvailableCount => _availableParticles.Count;
        public int TotalAllocated => _activeParticles.Count + _availableParticles.Count;

        public ParticlePool(int initialCapacity = 1000, int maxCapacity = 100000, int trailLength = 256)
        {
            _initialCapacity = initialCapacity;
            _maxCapacity = maxCapacity;
            _trailLength = trailLength;
            _availableParticles = new Stack<Particle>(initialCapacity);
            _activeParticles = new HashSet<Particle>();

            PreallocateParticles(initialCapacity);
        }

        private void PreallocateParticles(int count)
        {
            for (int i = 0; i < count; i++)
            {
                Particle particle = new Particle(-1, Vector3.zero, 0f, _trailLength);
                _availableParticles.Push(particle);
            }
        }

        public Particle Get(int id, Vector3 position, float time)
        {
            Particle particle;
            
            if (_availableParticles.Count > 0)
            {
                particle = _availableParticles.Pop();
                particle.Reset(position, time);
                particle.Data.ID = id;
            }
            else
            {
                if (TotalAllocated >= _maxCapacity)
                {
                    return null;
                }

                int newCount = Mathf.Min(100, _maxCapacity - TotalAllocated);
                PreallocateParticles(newCount);
                particle = _availableParticles.Pop();
                particle.Reset(position, time);
                particle.Data.ID = id;
            }

            _activeParticles.Add(particle);
            return particle;
        }

        public void Release(Particle particle)
        {
            if (particle == null) return;
            
            if (_activeParticles.Remove(particle))
            {
                particle.Data.IsAlive = false;
                particle.Trail.Clear();
                particle.Integrator = null;
                _availableParticles.Push(particle);
            }
        }

        public void ReleaseAll()
        {
            List<Particle> toRelease = new List<Particle>(_activeParticles);
            foreach (var particle in toRelease)
            {
                Release(particle);
            }
        }

        public void Clear()
        {
            _availableParticles.Clear();
            _activeParticles.Clear();
        }

        public void TrimExcess()
        {
            int targetCount = Mathf.Max(_initialCapacity, _activeParticles.Count * 2);
            
            while (_availableParticles.Count > targetCount)
            {
                _availableParticles.Pop();
            }
        }
    }

    public struct CircularBuffer<T>
    {
        private T[] _buffer;
        private int _head;
        private int _tail;
        private int _count;
        private readonly int _capacity;

        public int Count => _count;
        public int Capacity => _capacity;
        public bool IsFull => _count == _capacity;
        public bool IsEmpty => _count == 0;

        public CircularBuffer(int capacity)
        {
            _capacity = capacity;
            _buffer = new T[capacity];
            _head = 0;
            _tail = 0;
            _count = 0;
        }

        public void Add(T item)
        {
            _buffer[_tail] = item;
            _tail = (_tail + 1) % _capacity;

            if (_count < _capacity)
            {
                _count++;
            }
            else
            {
                _head = (_head + 1) % _capacity;
            }
        }

        public T this[int index]
        {
            get
            {
                if (index < 0 || index >= _count)
                    throw new System.IndexOutOfRangeException();
                
                return _buffer[(_head + index) % _capacity];
            }
        }

        public void Clear()
        {
            _head = 0;
            _tail = 0;
            _count = 0;
        }

        public T[] ToArray()
        {
            T[] result = new T[_count];
            for (int i = 0; i < _count; i++)
            {
                result[i] = this[i];
            }
            return result;
        }

        public void CopyTo(T[] array, int arrayIndex)
        {
            for (int i = 0; i < _count; i++)
            {
                array[arrayIndex + i] = this[i];
            }
        }

        public T GetLatest()
        {
            if (_count == 0)
                throw new System.InvalidOperationException("Buffer is empty");
            
            int index = (_tail - 1 + _capacity) % _capacity;
            return _buffer[index];
        }
    }
}
