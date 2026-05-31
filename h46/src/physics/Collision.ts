import { Vector3, Particle, CollisionResult, BoundaryBox, createVector3, vecAdd, vecSub, vecDot, vecScale, vecNormalize, vecLength } from '../types/physics';
import * as THREE from 'three';

export class CollisionDetector {
  private boundary: BoundaryBox;
  private bridgeMesh: THREE.Mesh | null = null;
  private bridgeBoundingBox: THREE.Box3 | null = null;
  private terrainHeights: number[][] | null = null;
  private terrainParams: { width: number; depth: number; resolution: number } | null = null;

  constructor(boundary: BoundaryBox) {
    this.boundary = boundary;
  }

  setBoundary(boundary: BoundaryBox): void {
    this.boundary = boundary;
  }

  setBridgeMesh(mesh: THREE.Mesh): void {
    this.bridgeMesh = mesh;
    this.bridgeBoundingBox = new THREE.Box3().setFromObject(mesh);
  }

  setTerrain(heights: number[][], params: { width: number; depth: number; resolution: number }): void {
    this.terrainHeights = heights;
    this.terrainParams = params;
  }

  getTerrainHeight(x: number, z: number): number {
    if (!this.terrainHeights || !this.terrainParams) {
      return this.boundary.min.y;
    }

    const { width, depth, resolution } = this.terrainParams;
    
    const nx = ((x + width / 2) / width) * (resolution - 1);
    const nz = ((z + depth / 2) / depth) * (resolution - 1);
    
    const ix = Math.max(0, Math.min(resolution - 2, Math.floor(nx)));
    const iz = Math.max(0, Math.min(resolution - 2, Math.floor(nz)));
    
    const fx = nx - ix;
    const fz = nz - iz;
    
    const h00 = this.terrainHeights[ix][iz];
    const h10 = this.terrainHeights[ix + 1][iz];
    const h01 = this.terrainHeights[ix][iz + 1];
    const h11 = this.terrainHeights[ix + 1][iz + 1];
    
    const h0 = h00 * (1 - fx) + h10 * fx;
    const h1 = h01 * (1 - fx) + h11 * fx;
    
    return h0 * (1 - fz) + h1 * fz;
  }

  checkTerrainCollision(particle: Particle, particleRadius: number): CollisionResult {
    const terrainY = this.getTerrainHeight(particle.position.x, particle.position.z);
    const particleBottom = particle.position.y - particleRadius;
    
    if (particleBottom < terrainY) {
      const penetration = terrainY - particleBottom;
      const normal = createVector3(0, 1, 0);
      
      return {
        collided: true,
        normal,
        penetration,
        point: createVector3(
          particle.position.x,
          terrainY,
          particle.position.z
        )
      };
    }
    
    return {
      collided: false,
      normal: createVector3(),
      penetration: 0,
      point: createVector3()
    };
  }

  checkBoundaryCollision(particle: Particle, particleRadius: number): CollisionResult {
    const { min, max } = this.boundary;
    let minPenetration = Infinity;
    let collisionNormal = createVector3();
    let collisionPoint = createVector3();
    let collided = false;

    if (particle.position.x - particleRadius < min.x) {
      const penetration = min.x - (particle.position.x - particleRadius);
      if (penetration < minPenetration) {
        minPenetration = penetration;
        collisionNormal = createVector3(1, 0, 0);
        collisionPoint = createVector3(min.x, particle.position.y, particle.position.z);
        collided = true;
      }
    }
    if (particle.position.x + particleRadius > max.x) {
      const penetration = (particle.position.x + particleRadius) - max.x;
      if (penetration < minPenetration) {
        minPenetration = penetration;
        collisionNormal = createVector3(-1, 0, 0);
        collisionPoint = createVector3(max.x, particle.position.y, particle.position.z);
        collided = true;
      }
    }
    if (particle.position.y - particleRadius < min.y) {
      const penetration = min.y - (particle.position.y - particleRadius);
      if (penetration < minPenetration) {
        minPenetration = penetration;
        collisionNormal = createVector3(0, 1, 0);
        collisionPoint = createVector3(particle.position.x, min.y, particle.position.z);
        collided = true;
      }
    }
    if (particle.position.y + particleRadius > max.y) {
      const penetration = (particle.position.y + particleRadius) - max.y;
      if (penetration < minPenetration) {
        minPenetration = penetration;
        collisionNormal = createVector3(0, -1, 0);
        collisionPoint = createVector3(particle.position.x, max.y, particle.position.z);
        collided = true;
      }
    }
    if (particle.position.z - particleRadius < min.z) {
      const penetration = min.z - (particle.position.z - particleRadius);
      if (penetration < minPenetration) {
        minPenetration = penetration;
        collisionNormal = createVector3(0, 0, 1);
        collisionPoint = createVector3(particle.position.x, particle.position.y, min.z);
        collided = true;
      }
    }
    if (particle.position.z + particleRadius > max.z) {
      const penetration = (particle.position.z + particleRadius) - max.z;
      if (penetration < minPenetration) {
        minPenetration = penetration;
        collisionNormal = createVector3(0, 0, -1);
        collisionPoint = createVector3(particle.position.x, particle.position.y, max.z);
        collided = true;
      }
    }

    return {
      collided,
      normal: collisionNormal,
      penetration: minPenetration,
      point: collisionPoint
    };
  }

  checkBridgeCollision(particle: Particle, particleRadius: number): CollisionResult {
    if (!this.bridgeMesh || !this.bridgeBoundingBox) {
      return {
        collided: false,
        normal: createVector3(),
        penetration: 0,
        point: createVector3()
      };
    }

    const particlePos = new THREE.Vector3(
      particle.position.x,
      particle.position.y,
      particle.position.z
    );

    const closestPoint = new THREE.Vector3();
    const distance = this.bridgeBoundingBox.distanceToPoint(particlePos);
    
    const detectionRadius = particleRadius * 3;
    if (distance > detectionRadius) {
      return {
        collided: false,
        normal: createVector3(),
        penetration: 0,
        point: createVector3()
      };
    }

    this.bridgeBoundingBox.clampPoint(particlePos, closestPoint);
    
    const toParticle = vecSub(
      { x: particlePos.x, y: particlePos.y, z: particlePos.z },
      { x: closestPoint.x, y: closestPoint.y, z: closestPoint.z }
    );
    
    const dist = vecLength(toParticle);
    
    if (dist < particleRadius * 1.5) {
      let normal: Vector3;
      if (dist > 1e-10) {
        normal = vecNormalize(toParticle);
      } else {
        const center = new THREE.Vector3();
        this.bridgeBoundingBox.getCenter(center);
        const toCenter = vecSub(
          { x: particlePos.x, y: particlePos.y, z: particlePos.z },
          { x: center.x, y: center.y, z: center.z }
        );
        normal = vecNormalize(toCenter);
      }
      
      const penetration = particleRadius - dist;
      
      return {
        collided: true,
        normal,
        penetration,
        point: { x: closestPoint.x, y: closestPoint.y, z: closestPoint.z }
      };
    }

    return {
      collided: false,
      normal: createVector3(),
      penetration: 0,
      point: createVector3()
    };
  }

  resolveCollision(
    particle: Particle,
    collision: CollisionResult,
    restitution: number = 0.1,
    friction: number = 0.3
  ): { velocityDelta: Vector3; positionDelta: Vector3 } {
    if (!collision.collided) {
      return {
        velocityDelta: createVector3(),
        positionDelta: createVector3()
      };
    }

    const positionDelta = vecScale(collision.normal, collision.penetration * 1.01);
    
    const vn = vecDot(particle.velocity, collision.normal);
    
    let velocityDelta = createVector3();
    if (vn < 0) {
      const normalComponent = vecScale(collision.normal, -(1 + restitution) * vn);
      
      const tangentVelocity = vecSub(particle.velocity, vecScale(collision.normal, vn));
      const tangentSpeed = vecLength(tangentVelocity);
      
      const frictionComponent = tangentSpeed > 1e-10 
        ? vecScale(tangentVelocity, -friction / tangentSpeed)
        : createVector3();
      
      velocityDelta = vecAdd(normalComponent, frictionComponent);
    }

    return { velocityDelta, positionDelta };
  }

  checkParticleCollision(p1: Particle, p2: Particle, particleRadius: number): boolean {
    const dx = p1.position.x - p2.position.x;
    const dy = p1.position.y - p2.position.y;
    const dz = p1.position.z - p2.position.z;
    const minDist = particleRadius * 2;
    return dx * dx + dy * dy + dz * dz < minDist * minDist;
  }

  getBridgeBoundingBox(): { min: Vector3; max: Vector3 } | null {
    if (!this.bridgeBoundingBox) return null;
    return {
      min: { x: this.bridgeBoundingBox.min.x, y: this.bridgeBoundingBox.min.y, z: this.bridgeBoundingBox.min.z },
      max: { x: this.bridgeBoundingBox.max.x, y: this.bridgeBoundingBox.max.y, z: this.bridgeBoundingBox.max.z }
    };
  }
}
