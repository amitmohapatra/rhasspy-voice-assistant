/**
 * Realistic 3D Avatar Manager - Indian Woman with Saree
 * Uses singleton pattern for optimal performance
 */
class AvatarManager {
    static instance = null;
    
    constructor() {
        if (AvatarManager.instance) {
            return AvatarManager.instance;
        }
        
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.avatar = null;
        this.mixer = null;
        this.currentEmotion = 'friendly';
        this.isSpeaking = false;
        this.isAwake = false;
        this.animationFrame = null;
        this.audioContext = null;
        this.analyser = null;
        this.audioSource = null;
        this.lipSyncInterval = null;
        this.streamingAnimation = null; // Animation for streaming tokens
        this.tokenReactionTimeout = null; // Timeout for token reactions
        this.leftArm = null; // Left arm bone for namaste gesture
        this.rightArm = null; // Right arm bone for namaste gesture
        this.leftHand = null; // Left hand bone
        this.rightHand = null; // Right hand bone
        
        AvatarManager.instance = this;
    }
    
    static getInstance() {
        if (!AvatarManager.instance) {
            AvatarManager.instance = new AvatarManager();
        }
        return AvatarManager.instance;
    }
    
    init() {
        const canvas = document.getElementById('avatar-canvas');
        if (!canvas) return;
        
        if (THREE && THREE.Cache) {
            THREE.Cache.enabled = true;
        }
        
        // Scene setup with realistic lighting
        this.scene = new THREE.Scene();
        // Make background transparent so CSS gradients show through
        this.scene.background = null;
        
        // Camera setup - optimized for face close-up
        this.camera = new THREE.PerspectiveCamera(
            30, // Narrower FOV for tighter face focus
            canvas.clientWidth / canvas.clientHeight,
            0.1,
            1000
        );
        // Position camera for portrait-style view (like HeyGen)
        // Camera will be adjusted after model loads to match avatar position
        this.camera.position.set(0, 1.0, 2.5);
        this.camera.lookAt(0, 1.0, 0);
        
        // High-quality renderer
        this.renderer = new THREE.WebGLRenderer({ 
            canvas: canvas,
            antialias: true,
            alpha: true,
            powerPreference: "high-performance"
        });
        this.renderer.setSize(canvas.clientWidth, canvas.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.2;
        // Note: outputEncoding and physicallyCorrectLights may not be available in r128
        try {
            if (this.renderer.outputEncoding !== undefined) {
                this.renderer.outputEncoding = THREE.sRGBEncoding;
            }
            if (this.renderer.physicallyCorrectLights !== undefined) {
                this.renderer.physicallyCorrectLights = true;
            }
        } catch (e) {
            console.log('Some renderer properties not available in this Three.js version:', e);
        }
        
        // Elegant lighting setup
        this.setupLighting();
        
        // Load realistic GLTF avatar model
        this.loadGLTFAvatar();
        
        // Setup audio context for lip sync
        this.setupAudioContext();
        
        // Handle window resize
        window.addEventListener('resize', () => this.handleResize());
        
        // Start render loop
        this.animate();
    }
    
    setupLighting() {
        // Realistic studio lighting setup (like HeyGen)
        
        // Create a simple environment map using a cube texture (simplified for r128)
        // For now, we'll create a basic cube texture
        const envMap = this.createSimpleEnvironmentMap();
        
        // Soft ambient light for base illumination
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
        this.scene.add(ambientLight);
        
        // Main key light (studio quality, from front-right)
        const keyLight = new THREE.DirectionalLight(0xffffff, 2.0);
        keyLight.position.set(3, 5, 4);
        keyLight.castShadow = true;
        keyLight.shadow.mapSize.width = 4096;
        keyLight.shadow.mapSize.height = 4096;
        keyLight.shadow.camera.near = 0.1;
        keyLight.shadow.camera.far = 100;
        keyLight.shadow.camera.left = -3;
        keyLight.shadow.camera.right = 3;
        keyLight.shadow.camera.top = 3;
        keyLight.shadow.camera.bottom = -3;
        keyLight.shadow.bias = -0.0001;
        keyLight.shadow.normalBias = 0.02;
        this.scene.add(keyLight);
        
        // Fill light (soft, from left)
        const fillLight = new THREE.DirectionalLight(0xffffff, 0.8);
        fillLight.position.set(-2, 3, 2);
        this.scene.add(fillLight);
        
        // Back/rim light for separation (from behind)
        const rimLight = new THREE.DirectionalLight(0xffffff, 0.6);
        rimLight.position.set(-1, 2, -3);
        this.scene.add(rimLight);
        
        // Additional soft area light for face
        const faceLight = new THREE.PointLight(0xffffff, 1.0);
        faceLight.position.set(0, 1.8, 2.5);
        faceLight.decay = 2;
        this.scene.add(faceLight);
        
        // Store for environment mapping
        this.envMap = envMap;
    }
    
    createSimpleEnvironmentMap() {
        // Create a simple environment map using a canvas texture
        // This is a fallback for when PMREMGenerator is not available
        try {
            const canvas = document.createElement('canvas');
            canvas.width = 256;
            canvas.height = 256;
            const ctx = canvas.getContext('2d');
            
            // Create a simple gradient for environment
            const gradient = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
            gradient.addColorStop(0, '#ffffff');
            gradient.addColorStop(1, '#e0e0e0');
            ctx.fillStyle = gradient;
            ctx.fillRect(0, 0, 256, 256);
            
            const texture = new THREE.CanvasTexture(canvas);
            texture.mapping = THREE.CubeReflectionMapping;
            return texture;
        } catch (e) {
            console.warn('Could not create environment map:', e);
            return null; // Return null if creation fails
        }
    }
    
    async loadGLTFAvatar() {
        // Load a realistic GLTF avatar model
        // Using a free open-source model from a public repository
        const loader = new THREE.GLTFLoader();
        
        // Option 1: Use a free model from a CDN (you'll need to replace this URL)
        // Download a free GLTF model from:
        // - Sketchfab (filter by "Downloadable" and "Free", CC-BY license)
        // - MakeHuman (export as GLTF) - makehuman.org
        // - Free3D.com
        // - Clara.io
        // Then host it or use a CDN URL
        
        // Load the GLB model from the models folder
        // Add cache busting to force reload
        const modelUrl = 'models/indian_woman_in_saree.glb';
        
        console.log('🔄 Loading GLTF model:', modelUrl, 'at', new Date().toISOString());
        
        try {
            const gltf = await new Promise((resolve, reject) => {
                loader.load(
                    modelUrl,
                    (gltf) => resolve(gltf),
                    (progress) => {
                        if (progress.total > 0) {
                            console.log('Loading model:', (progress.loaded / progress.total * 100).toFixed(1) + '%');
                        }
                    },
                    (error) => {
                        console.warn('Failed to load GLTF model, using fallback:', error);
                        reject(error);
                    }
                );
            });
            
            // Model loaded successfully
            this.avatar = gltf.scene;
            
            // Keep model's original orientation - don't force rotations
            
            // Calculate appropriate scale and position
            // First, compute bounding box to center the model
            const box = new THREE.Box3().setFromObject(this.avatar);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            
            // Scale to focus on face - much smaller scale for smaller avatar
            const maxDim = Math.max(size.x, size.y, size.z);
            const baseScale = 2.9 / size.y; // Slightly smaller scale
            // Keep proportions balanced
            const scaleX = baseScale;
            const scaleY = baseScale;
            const scaleZ = baseScale;
            this.avatar.scale.set(scaleX, scaleY, scaleZ);
            
            // Log essential model info
            console.log('📐 Model loaded - Size:', size.y.toFixed(2), 'Scale:', baseScale.toFixed(2));
            
            // Center the model and position for face focus - DRAG IT DOWN BIG
            const lowerOffset = -5.5; // Position avatar WAY DOWN - increased more
            const finalY = -center.y * scaleY + lowerOffset;
            this.avatar.position.set(-center.x * scaleX, finalY, -center.z * scaleZ);
            console.log('📐 Avatar Y position set to:', finalY.toFixed(2), '(should be negative/low)');
            
            // Log essential positioning
            console.log('📐 Avatar positioned - Y:', this.avatar.position.y.toFixed(2));
            
            // Ensure model is upright and facing camera - don't modify rotations
            // Keep original rotations from model to prevent distortion
            
            // Enable shadows and ensure proper material rendering
            let meshCount = 0;
            this.avatar.traverse((child) => {
                if (child.isMesh) {
                    meshCount++;
                    child.castShadow = true;
                    child.receiveShadow = true;
                    child.visible = true; // Ensure mesh is visible
                    
                    // Check if this is a hair mesh and change color to black
                    const meshName = child.name.toLowerCase();
                    
                    // EXCLUDE face/head/skin meshes first
                    const isFaceOrSkin = meshName.includes('face') || 
                                        meshName.includes('skin') ||
                                        meshName.includes('head') && !meshName.includes('hair') ||
                                        meshName.includes('eye') ||
                                        meshName.includes('nose') ||
                                        meshName.includes('mouth') ||
                                        meshName.includes('lip') ||
                                        meshName.includes('cheek') ||
                                        meshName.includes('forehead');
                    
                    // Only detect hair if it's NOT face/skin
                    const isHair = !isFaceOrSkin && (
                        meshName.includes('hair') || 
                        meshName.includes('scalp') ||
                        meshName.includes('ponytail') ||
                        meshName.includes('bun') ||
                        meshName.includes('braid') ||
                        meshName.includes('wig') ||
                        meshName.includes('pony') ||
                        meshName.includes('lock')
                    );
                    
                    // Ensure materials are properly set up for saree model
                    if (child.material) {
                        if (Array.isArray(child.material)) {
                            child.material.forEach(mat => {
                                if (mat) {
                                    mat.needsUpdate = true;
                                    mat.side = THREE.DoubleSide; // Use DoubleSide for saree model
                                    mat.transparent = false;
                                    
                                    // Change hair color to black - ONLY if it's hair, NOT face
                                    if (isHair) {
                                        mat.color = new THREE.Color(0x000000); // Pure black
                                        mat.emissive = new THREE.Color(0x000000); // No glow
                                        console.log('🎨 Changed hair color to black for:', child.name);
                                    }
                                    
                                    if (mat.map) {
                                        mat.map.needsUpdate = true;
                                        mat.map.flipY = false;
                                    }
                                }
                            });
                        } else {
                            child.material.needsUpdate = true;
                            child.material.side = THREE.DoubleSide; // Use DoubleSide for saree model
                            child.material.transparent = false;
                            
                            // Change hair color to black - ONLY if it's hair, NOT face
                            if (isHair) {
                                child.material.color = new THREE.Color(0x000000); // Pure black
                                child.material.emissive = new THREE.Color(0x000000); // No glow
                                console.log('🎨 Changed hair color to black for:', child.name);
                            }
                            
                            if (child.material.map) {
                                child.material.map.needsUpdate = true;
                                child.material.map.flipY = false;
                            }
                        }
                    }
                    
                    // Ensure geometry is valid and visible
                    if (child.geometry) {
                        child.geometry.computeBoundingBox();
                        child.geometry.computeBoundingSphere();
                        child.geometry.computeVertexNormals();
                    }
                }
            });
            
            console.log(`✅ Found ${meshCount} meshes in model`);
            
            // Find and store references for animation
            this.findAvatarParts();
            
            // Position camera to focus on FACE, not body
            // Calculate face position from avatar bounding box (more reliable)
            const avatarBox = new THREE.Box3().setFromObject(this.avatar);
            const avatarMaxY = avatarBox.max.y;
            const avatarMinY = avatarBox.min.y;
            const avatarHeight = avatarMaxY - avatarMinY;
            // Face is in upper portion - use 85% from bottom (top 15% of avatar)
            const targetFaceY = avatarMinY + (avatarHeight * 0.85);
            console.log('📐 Avatar bounds - min Y:', avatarMinY.toFixed(2), 'max Y:', avatarMaxY.toFixed(2));
            console.log('📐 Calculated face Y position:', targetFaceY.toFixed(2));
            
            // Position camera lower to account for avatar being dragged down
            // Camera should be below viewport center to avoid browser search bar
            const cameraY = Math.min(targetFaceY, -0.2); // Use face Y or -0.2, whichever is lower
            this.camera.position.set(0, cameraY, 2.0); // At calculated position, 2 units away
            this.camera.lookAt(0, targetFaceY, 0); // Look directly at face
            console.log('📷 Camera Y:', cameraY.toFixed(2), 'looking at face Y:', targetFaceY.toFixed(2));
            
            // Add forward tilt to head so face looks straight (not up)
            // In Three.js: positive X rotation = head tilts forward/down
            if (this.head) {
                this._baseHeadTiltX = 0.4; // Strong forward tilt to look straight ahead
                this.head.rotation.x = this._baseHeadTiltX;
                console.log('👤 Head rotated forward (X):', this._baseHeadTiltX, 'radians');
            }
            
            console.log('📷 Camera positioned at face level - Y:', targetFaceY.toFixed(2), 'distance: 2.0');
            
            // Add to scene
            this.scene.add(this.avatar);
            
            // Set up animations if available
            if (gltf.animations && gltf.animations.length > 0) {
                this.mixer = new THREE.AnimationMixer(this.avatar);
                gltf.animations.forEach((clip) => {
                    this.mixer.clipAction(clip).play();
                });
            }
            
            // Reset base position for breathing animation to use the new lower position
            this._baseAvatarY = this.avatar.position.y;
            
            // Set awake state
            this.setAwake(true);
            
            console.log('✅ GLTF avatar loaded successfully:', modelUrl);
            console.log('✅ Avatar added to scene, ready for rendering');
            console.log('✅ Avatar Y position:', this.avatar.position.y, 'Base Y:', this._baseAvatarY);
        } catch (error) {
            console.error('❌ Error loading GLTF avatar:', error);
            console.error('Error details:', {
                message: error.message,
                stack: error.stack,
                modelUrl: modelUrl
            });
            // Don't fallback - show error to user
            alert(`Failed to load avatar model: ${error.message}. Please check console for details.`);
        }
    }
    
    findAvatarParts() {
        // Find head, eyes, mouth in the loaded model for lip sync
        if (!this.avatar) return;
        
        console.log('🔍 Searching for avatar parts in GLTF model...');
        
        const allMeshes = [];
        let headCandidate = null;
        let headY = 0;
        let headZ = 0;
        
        // First pass: collect all meshes and find head
        this.avatar.traverse((child) => {
            if (child.isMesh) {
                const name = child.name.toLowerCase();
                allMeshes.push(child);
                
                // Log all mesh names for debugging
                if (name && name.length > 0) {
                    console.log('  Found mesh:', name);
                }
                
                // Find head (try multiple variations)
                if (!this.head) {
                    if (name.includes('head') || name.includes('face') || name.includes('skull')) {
                        this.head = child;
                        headCandidate = child;
                        const pos = new THREE.Vector3();
                        child.getWorldPosition(pos);
                        headY = pos.y;
                        headZ = pos.z;
                        console.log('  ✓ Found head:', name);
                    }
                }
                
                // Find eyes (try multiple variations)
                if (name.includes('eye') || name.includes('eyeball') || name.includes('iris')) {
                    if (!this.eyes) this.eyes = {};
                    if (name.includes('left') || name.includes('l') || name.includes('_l')) {
                        this.eyes.left = child;
                        console.log('  ✓ Found left eye:', name);
                    } else if (name.includes('right') || name.includes('r') || name.includes('_r')) {
                        this.eyes.right = child;
                        console.log('  ✓ Found right eye:', name);
                    } else if (!this.eyes.left) {
                        this.eyes.left = child;
                        console.log('  ✓ Found eye (assumed left):', name);
                    } else if (!this.eyes.right) {
                        this.eyes.right = child;
                        console.log('  ✓ Found eye (assumed right):', name);
                    }
                }
                
                // Find mouth (try multiple variations)
                if (!this.mouth) {
                    if (name.includes('mouth') || name.includes('lip') || name.includes('jaw') || 
                        name.includes('teeth') || name.includes('tongue')) {
                        this.mouth = child;
                        console.log('  ✓ Found mouth:', name);
                    }
                }
            }
            
            // Find bones for arm animations (namaste gesture) - Enhanced detection
            if (child.isBone || child.type === 'Bone') {
                const boneName = child.name.toLowerCase();
                
                // Find left arm/hand bones (more flexible matching)
                if ((boneName.includes('left') || boneName.includes('l_') || boneName.includes('lhand') || boneName.includes('larm')) && 
                    (boneName.includes('arm') || boneName.includes('upperarm') || boneName.includes('shoulder') || boneName.includes('hand') || boneName.includes('wrist'))) {
                    if (boneName.includes('arm') || boneName.includes('upperarm') || boneName.includes('shoulder')) {
                        if (!this.leftArm) {
                            this.leftArm = child;
                            console.log('  ✓ Found left arm bone:', child.name);
                        }
                    }
                    if (boneName.includes('hand') || boneName.includes('wrist')) {
                        if (!this.leftHand) {
                            this.leftHand = child;
                            console.log('  ✓ Found left hand bone:', child.name);
                        }
                    }
                }
                
                // Find right arm/hand bones (more flexible matching)
                if ((boneName.includes('right') || boneName.includes('r_') || boneName.includes('rhand') || boneName.includes('rarm')) && 
                    (boneName.includes('arm') || boneName.includes('upperarm') || boneName.includes('shoulder') || boneName.includes('hand') || boneName.includes('wrist'))) {
                    if (boneName.includes('arm') || boneName.includes('upperarm') || boneName.includes('shoulder')) {
                        if (!this.rightArm) {
                            this.rightArm = child;
                            console.log('  ✓ Found right arm bone:', child.name);
                        }
                    }
                    if (boneName.includes('hand') || boneName.includes('wrist')) {
                        if (!this.rightHand) {
                            this.rightHand = child;
                            console.log('  ✓ Found right hand bone:', child.name);
                        }
                    }
                }
            }
            
            // Also check skinned meshes for bones
            if (child.isSkinnedMesh && child.skeleton) {
                child.skeleton.bones.forEach(bone => {
                    const boneName = bone.name.toLowerCase();
                    if ((boneName.includes('left') || boneName.includes('l_')) && 
                        (boneName.includes('arm') || boneName.includes('upperarm'))) {
                        if (!this.leftArm) {
                            this.leftArm = bone;
                            console.log('  ✓ Found left arm bone from skeleton:', bone.name);
                        }
                    }
                    if ((boneName.includes('left') || boneName.includes('l_')) && 
                        (boneName.includes('hand') || boneName.includes('wrist'))) {
                        if (!this.leftHand) {
                            this.leftHand = bone;
                            console.log('  ✓ Found left hand bone from skeleton:', bone.name);
                        }
                    }
                    if ((boneName.includes('right') || boneName.includes('r_')) && 
                        (boneName.includes('arm') || boneName.includes('upperarm'))) {
                        if (!this.rightArm) {
                            this.rightArm = bone;
                            console.log('  ✓ Found right arm bone from skeleton:', bone.name);
                        }
                    }
                    if ((boneName.includes('right') || boneName.includes('r_')) && 
                        (boneName.includes('hand') || boneName.includes('wrist'))) {
                        if (!this.rightHand) {
                            this.rightHand = bone;
                            console.log('  ✓ Found right hand bone from skeleton:', bone.name);
                        }
                    }
                });
            }
        });
        
        // If head not found by name, find the largest/most central mesh as head
        if (!this.head && allMeshes.length > 0) {
            console.log('  ⚠️ Head not found by name, finding largest mesh...');
            let largestMesh = null;
            let maxSize = 0;
            
            allMeshes.forEach(mesh => {
                const box = new THREE.Box3().setFromObject(mesh);
                const size = box.getSize(new THREE.Vector3());
                const volume = size.x * size.y * size.z;
                if (volume > maxSize) {
                    maxSize = volume;
                    largestMesh = mesh;
                }
            });
            
            if (largestMesh) {
                this.head = largestMesh;
                headCandidate = largestMesh;
                const pos = new THREE.Vector3();
                largestMesh.getWorldPosition(pos);
                headY = pos.y;
                headZ = pos.z;
                console.log('  ✓ Using largest mesh as head:', largestMesh.name || 'unnamed');
            }
        }
        
        // Enhanced detection: If eyes not found, try to find by position/size
        if ((!this.eyes || !this.eyes.left || !this.eyes.right) && headCandidate) {
            console.log('  ⚠️ Eyes not found by name, searching by position/size...');
            const headBox = new THREE.Box3().setFromObject(headCandidate);
            const headCenter = headBox.getCenter(new THREE.Vector3());
            const headSize = headBox.getSize(new THREE.Vector3());
            
            const eyeCandidates = [];
            allMeshes.forEach(mesh => {
                if (mesh === headCandidate) return;
                const meshBox = new THREE.Box3().setFromObject(mesh);
                const meshCenter = meshBox.getCenter(new THREE.Vector3());
                const meshSize = meshBox.getSize(new THREE.Vector3());
                
                const distance = meshCenter.distanceTo(headCenter);
                const sizeRatio = (meshSize.x + meshSize.y + meshSize.z) / (headSize.x + headSize.y + headSize.z);
                
                if (distance < headSize.y * 0.6 && sizeRatio < 0.15 && meshSize.y < headSize.y * 0.3) {
                    const deltaX = meshCenter.x - headCenter.x;
                    eyeCandidates.push({ mesh, deltaX, distance, sizeRatio });
                }
            });
            
            eyeCandidates.sort((a, b) => a.deltaX - b.deltaX);
            
            if (eyeCandidates.length >= 2) {
                if (!this.eyes) this.eyes = {};
                this.eyes.left = eyeCandidates[0].mesh;
                this.eyes.right = eyeCandidates[1].mesh;
                console.log('  ✓ Found eyes by position: left and right');
            } else if (eyeCandidates.length === 1) {
                if (!this.eyes) this.eyes = {};
                this.eyes.left = eyeCandidates[0].mesh;
                console.log('  ✓ Found one eye by position (using as left)');
            }
        }
        
        // If mouth not found by name, find by position (front and lower part of head)
        if (!this.mouth && headCandidate) {
            console.log('  ⚠️ Mouth not found by name, searching by position...');
            let bestMouth = null;
            let bestScore = -Infinity;
            
            const headBox = new THREE.Box3().setFromObject(headCandidate);
            const headCenter = headBox.getCenter(new THREE.Vector3());
            const headSize = headBox.getSize(new THREE.Vector3());
            
            allMeshes.forEach(mesh => {
                if (mesh === headCandidate) return;
                
                const meshBox = new THREE.Box3().setFromObject(mesh);
                const meshCenter = meshBox.getCenter(new THREE.Vector3());
                const meshSize = meshBox.getSize(new THREE.Vector3());
                
                // Calculate position relative to head
                const deltaY = headCenter.y - meshCenter.y; // Should be positive (mouth below head center)
                const deltaZ = meshCenter.z - headCenter.z; // Should be positive (mouth in front)
                const distance = meshCenter.distanceTo(headCenter);
                
                // Score: prefer meshes that are:
                // 1. Below head center (deltaY > 0)
                // 2. In front of head (deltaZ > 0)
                // 3. Close to head (small distance)
                // 4. Small to medium size (not too large)
                const sizeRatio = (meshSize.x + meshSize.y + meshSize.z) / (headSize.x + headSize.y + headSize.z);
                
                if (deltaY > 0 && deltaY < headSize.y * 0.6 && // Below but not too far
                    deltaZ > -headSize.z * 0.3 && // In front or slightly behind
                    distance < headSize.y * 0.8 && // Close to head
                    sizeRatio < 0.3) { // Not too large
                    
                    const score = (deltaY * 2) + (deltaZ * 1.5) - (distance * 0.5) - (sizeRatio * 10);
                    if (score > bestScore) {
                        bestScore = score;
                        bestMouth = mesh;
                    }
                }
            });
            
            if (bestMouth) {
                this.mouth = bestMouth;
                console.log('  ✓ Found mouth by position:', bestMouth.name || 'unnamed', `(score: ${bestScore.toFixed(2)})`);
            } else {
                // Last resort: use head itself for lip sync
                console.log('  ⚠️ Mouth not found, will use head mesh for lip sync');
                this.mouth = headCandidate;
            }
        }
        
        // If still no head, use entire avatar
        if (!this.head && this.avatar) {
            this.head = this.avatar;
            console.log('  ⚠️ Using entire avatar as head reference');
        }
        
        // If still no mouth, use head
        if (!this.mouth && this.head) {
            this.mouth = this.head;
            console.log('  ⚠️ Using head mesh for lip sync (mouth not found separately)');
        }
        
        // Summary with warnings
        console.log('📊 Avatar parts found:', {
            head: !!this.head,
            headName: this.head?.name || 'unnamed',
            leftEye: !!this.eyes?.left,
            rightEye: !!this.eyes?.right,
            mouth: !!this.mouth,
            mouthName: this.mouth?.name || 'unnamed',
            leftArm: !!this.leftArm,
            rightArm: !!this.rightArm,
            leftHand: !!this.leftHand,
            rightHand: !!this.rightHand
        });
        
        // Warn if critical parts are missing
        if (!this.mouth) {
            console.warn('⚠️ Mouth not found - lip sync may not work properly');
        }
        if (!this.eyes || !this.eyes.left || !this.eyes.right) {
            console.warn('⚠️ Eyes not found - blinking may not work properly');
        }
        if (!this.leftArm || !this.rightArm) {
            console.warn('⚠️ Arm bones not found - namaste gesture may not work');
        }
    }
    
    setupAudioContext() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.analyser.smoothingTimeConstant = 0.8;
        } catch (e) {
            console.warn('Audio context not available:', e);
        }
    }
    
    setAwake(awake) {
        this.isAwake = awake;
        if (awake) {
            this.wakeUp();
        } else {
            this.sleep();
        }
    }
    
    wakeUp() {
        // Smooth wake-up animation
        if (this.avatar) {
            const startY = this.avatar.position.y;
            const startRot = this.head ? this.head.rotation.x : 0;
            
            let progress = 0;
            const animate = () => {
                progress += 0.05;
                if (progress > 1) progress = 1;
                
                // Head maintains forward tilt during wake-up
                if (this.head) {
                    // Maintain forward tilt (base tilt is 0.3)
                    const baseTilt = this._baseHeadTiltX !== undefined ? this._baseHeadTiltX : 0.3;
                    this.head.rotation.x = baseTilt; // Keep forward tilt for face focus
                }
                
                // Eyes open wider
                if (this.eyes) {
                    this.eyes.left.scale.y = 0.3 + (0.7 * progress);
                    this.eyes.right.scale.y = 0.3 + (0.7 * progress);
                }
                
                // Subtle smile
                if (this.mouth) {
                    this.mouth.scale.x = 1.0 + (0.4 * progress);
                    this.mouth.scale.y = 0.6 + (0.2 * progress);
                }
                
                if (progress < 1) {
                    requestAnimationFrame(animate);
                }
            };
            animate();
        }
    }
    
    sleep() {
        // Idle/sleep state
        if (this.head) {
            this.head.rotation.x = 0.1;
        }
        if (this.eyes) {
            this.eyes.left.scale.y = 0.3;
            this.eyes.right.scale.y = 0.3;
        }
        if (this.mouth) {
            this.mouth.scale.x = 1.0;
            this.mouth.scale.y = 0.6;
        }
    }
    
    setEmotion(emotion, intensity = 0.5) {
        if (!this.isAwake) return;
        
        this.currentEmotion = emotion;
        if (!this.avatar) return;
        
        console.log('😊 Setting emotion:', emotion, 'intensity:', intensity);
        
        // Try to use morph targets first (for GLTF models with blend shapes)
        if (this.head && this.head.morphTargetInfluences && this.head.morphTargetInfluences.length > 0) {
            this.applyEmotionWithMorphTargets(emotion, intensity);
            return;
        }
        
        // Fallback to scale/rotation for models without morph targets
        const expressions = {
            'happy': () => {
                if (this.mouth) {
                    this.mouth.scale.y = 0.7;
                    this.mouth.scale.x = 1.8;
                }
                if (this.eyes) {
                    this.eyes.left.scale.y = 0.5;
                    this.eyes.right.scale.y = 0.5;
                }
                if (this.head) {
                    this.head.rotation.x = -0.12;
                }
            },
            'sad': () => {
                if (this.mouth) {
                    this.mouth.scale.y = 0.5;
                    this.mouth.scale.x = 1.1;
                    this.mouth.position.y = 1.51;
                }
                if (this.head) {
                    this.head.rotation.x = 0.15;
                }
            },
            'excited': () => {
                if (this.mouth) {
                    this.mouth.scale.y = 1.0;
                    this.mouth.scale.x = 2.0;
                }
                if (this.eyes) {
                    this.eyes.left.scale.y = 1.2;
                    this.eyes.right.scale.y = 1.2;
                }
            },
            'calm': () => {
                if (this.mouth) {
                    this.mouth.scale.y = 0.6;
                    this.mouth.scale.x = 1.2;
                }
            },
            'concerned': () => {
                if (this.mouth) {
                    this.mouth.scale.y = 0.5;
                    this.mouth.scale.x = 0.9;
                }
                if (this.head) {
                    this.head.rotation.x = 0.1;
                }
            },
            'friendly': () => {
                if (this.mouth) {
                    this.mouth.scale.y = 0.7;
                    this.mouth.scale.x = 1.4;
                }
                if (this.head) {
                    this.head.rotation.x = -0.05;
                }
            }
        };
        
        const applyExpression = expressions[emotion] || expressions['friendly'];
        applyExpression();
        
        if (intensity < 1.0 && this.mouth) {
                this.mouth.scale.multiplyScalar(0.7 + (intensity * 0.3));
        }
    }
    
    applyEmotionWithMorphTargets(emotion, intensity) {
        // Apply emotions using morph targets (blend shapes) for GLTF models
        if (!this.head || !this.head.morphTargetInfluences) return;
        
        // Reset all morph targets first
        for (let i = 0; i < this.head.morphTargetInfluences.length; i++) {
            this.head.morphTargetInfluences[i] = 0;
        }
        
        // Map emotions to common morph target names
        const emotionMappings = {
            'happy': ['smile', 'happy', 'joy', 'grin', 'cheerful'],
            'sad': ['sad', 'frown', 'sorrow', 'unhappy'],
            'excited': ['excited', 'surprised', 'wide', 'open'],
            'calm': ['neutral', 'calm', 'peaceful'],
            'concerned': ['worried', 'concerned', 'frown'],
            'friendly': ['smile', 'friendly', 'kind']
        };
        
        const targetNames = emotionMappings[emotion] || emotionMappings['friendly'];
        
        // Find and apply morph targets
        if (this.head.morphTargetDictionary) {
            for (const targetName of targetNames) {
                const targetIndex = this.head.morphTargetDictionary[targetName];
                if (targetIndex !== undefined) {
                    this.head.morphTargetInfluences[targetIndex] = intensity;
                    console.log(`  ✓ Applied morph target: ${targetName} (${intensity})`);
                }
            }
        } else {
            // Try to find by name pattern
            for (let i = 0; i < this.head.morphTargetInfluences.length; i++) {
                // This is a fallback - we don't have the dictionary
                // Just apply to first few targets as a guess
                if (i < targetNames.length) {
                    this.head.morphTargetInfluences[i] = intensity * 0.5;
                }
            }
        }
        
        // Also try to apply to mouth if it has morph targets
        if (this.mouth && this.mouth.morphTargetInfluences) {
            for (const targetName of targetNames) {
                if (this.mouth.morphTargetDictionary) {
                    const targetIndex = this.mouth.morphTargetDictionary[targetName];
                    if (targetIndex !== undefined) {
                        this.mouth.morphTargetInfluences[targetIndex] = intensity;
                    }
                }
            }
        }
    }
    
    startLipSync(audioBase64) {
        this.isSpeaking = true;
        
        if (!this.avatar) {
            console.warn('⚠️ Cannot start lip sync: avatar not loaded');
            return;
        }
        
        if (!this.mouth) {
            console.warn('⚠️ Mouth not found, trying to find it again...');
            this.findAvatarParts();
            if (!this.mouth) {
                console.warn('⚠️ Still no mouth found, using fallback lip sync');
                this.simpleLipSync();
                return;
            }
        }
        
        console.log('🎤 Starting lip sync, mouth found:', this.mouth.name || 'unnamed');
        
        const audio = new Audio(`data:audio/mpeg;base64,${audioBase64}`);
        
        // Play the audio first
        audio.play().catch(e => {
            console.error('Error playing audio for lip sync:', e);
        });
        
        if (this.audioContext && this.analyser) {
            try {
                // Create audio source and connect to analyser
            this.audioSource = this.audioContext.createMediaElementSource(audio);
            this.audioSource.connect(this.analyser);
            this.analyser.connect(this.audioContext.destination);
                console.log('✅ Audio analyser connected, starting lip sync analysis');
            this.analyzeAudioForLipSync();
            } catch (e) {
                console.warn('⚠️ Could not connect audio analyser, using simple lip sync:', e);
                this.simpleLipSync();
            }
        } else {
            console.log('⚠️ Audio context not available, using simple lip sync');
            this.simpleLipSync();
        }
    }
    
    analyzeAudioForLipSync() {
        if (!this.analyser || !this.isSpeaking) {
            console.warn('⚠️ Cannot analyze audio: analyser not available or not speaking');
            return;
        }
        
        const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        let frameCount = 0;
        
        const updateLipSync = () => {
            if (!this.isSpeaking) {
                console.log('🛑 Lip sync stopped (isSpeaking = false)');
                return;
            }
            
            if (!this.analyser) {
                console.warn('⚠️ Analyser lost, stopping lip sync');
                return;
            }
            
            this.analyser.getByteFrequencyData(dataArray);
            
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                sum += dataArray[i];
            }
            const average = sum / dataArray.length;
            const normalized = Math.min(average / 255, 1.0);
            
            // Log every 30 frames (about once per second at 60fps)
            if (frameCount % 30 === 0) {
                console.log(`🎤 Lip sync: avg=${average.toFixed(1)}, normalized=${normalized.toFixed(3)}`);
            }
            frameCount++;
            
            // Try multiple methods for lip sync with GLTF models
            if (this.mouth) {
                // Store original scale if not stored
                if (!this.mouth.userData.originalScale) {
                    this.mouth.userData.originalScale = {
                        x: this.mouth.scale.x,
                        y: this.mouth.scale.y,
                        z: this.mouth.scale.z
                    };
                }
                
                // Method 1: Scale (works for simple models) - Enhanced for visibility
                const baseScale = this.mouth.userData.originalScale.y || 1.0;
                const mouthOpen = baseScale + (normalized * 0.5); // More visible scale change
                this.mouth.scale.y = Math.max(0.3, mouthOpen); // Ensure minimum visibility
                this.mouth.scale.x = (this.mouth.userData.originalScale.x || 1.0) + (normalized * 0.3);
                
                // Method 2: Try morph targets if available
                if (this.mouth.morphTargetInfluences && this.mouth.morphTargetInfluences.length > 0) {
                    // Find mouth open morph target
                    for (let i = 0; i < this.mouth.morphTargetInfluences.length; i++) {
                        const targetName = this.mouth.morphTargetDictionary 
                            ? Object.keys(this.mouth.morphTargetDictionary).find(
                                key => this.mouth.morphTargetDictionary[key] === i
                            )?.toLowerCase() || ''
                            : '';
                        
                        if (targetName.includes('open') || targetName.includes('mouth') || 
                            targetName.includes('ah') || targetName.includes('oh') ||
                            targetName.includes('jaw') || targetName.includes('speak')) {
                            this.mouth.morphTargetInfluences[i] = normalized * 0.8;
                        }
                    }
                }
                
                // Method 3: Position adjustment (subtle)
                if (this.mouth.position) {
                    const originalZ = this.mouth.userData.originalZ || this.mouth.position.z;
                    if (!this.mouth.userData.originalZ) {
                        this.mouth.userData.originalZ = originalZ;
                    }
                    this.mouth.position.z = originalZ + (normalized * 0.02);
                }
            } else if (this.head) {
                // Fallback: animate head slightly
                const headRot = (normalized * 0.05) - 0.025;
                this.head.rotation.x += (headRot - this.head.rotation.x) * 0.1; // Smooth interpolation
            }
            
            requestAnimationFrame(updateLipSync);
        };
        
        console.log('🎬 Starting lip sync animation loop');
        updateLipSync();
    }
    
    simpleLipSync() {
        let frame = 0;
        // Store original scale if not stored
        if (this.mouth && !this.mouth.userData.originalScale) {
            this.mouth.userData.originalScale = {
                x: this.mouth.scale.x,
                y: this.mouth.scale.y,
                z: this.mouth.scale.z
            };
        }
        
        this.lipSyncInterval = setInterval(() => {
            if (!this.isSpeaking || !this.mouth) {
                clearInterval(this.lipSyncInterval);
                this.lipSyncInterval = null;
                // Reset mouth to original scale
                if (this.mouth && this.mouth.userData.originalScale) {
                    this.mouth.scale.y = this.mouth.userData.originalScale.y;
                    this.mouth.scale.x = this.mouth.userData.originalScale.x;
                }
                return;
            }
            
            frame++;
            const baseY = this.mouth.userData.originalScale?.y || 0.7;
            const baseX = this.mouth.userData.originalScale?.x || 1.4;
            // More visible lip sync animation
            const mouthOpen = baseY + Math.sin(frame * 0.4) * 0.4;
            this.mouth.scale.y = Math.max(0.3, mouthOpen);
            this.mouth.scale.x = baseX + Math.sin(frame * 0.3) * 0.3;
        }, 50);
    }
    
    // Namaste gesture animation
    performNamaste(duration = 2000) {
        if (!this.isAwake) return;
        
        console.log('🙏 Performing Namaste gesture');
        
        // Store original rotations
        const originalLeftArmRot = this.leftArm ? this.leftArm.rotation.clone() : null;
        const originalRightArmRot = this.rightArm ? this.rightArm.rotation.clone() : null;
        const originalLeftHandRot = this.leftHand ? this.leftHand.rotation.clone() : null;
        const originalRightHandRot = this.rightHand ? this.rightHand.rotation.clone() : null;
        
        const startTime = Date.now();
        const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease in-out animation
            const ease = progress < 0.5 
                ? 2 * progress * progress 
                : 1 - Math.pow(-2 * progress + 2, 2) / 2;
            
            if (progress < 1) {
                // Bring hands together in namaste position
                if (this.leftArm) {
                    // Rotate left arm forward and up
                    this.leftArm.rotation.x = -0.5 * ease; // Forward
                    this.leftArm.rotation.z = 0.3 * ease; // Slight outward
                }
                if (this.rightArm) {
                    // Rotate right arm forward and up
                    this.rightArm.rotation.x = -0.5 * ease; // Forward
                    this.rightArm.rotation.z = -0.3 * ease; // Slight outward
                }
                if (this.leftHand) {
                    // Rotate left hand to meet right
                    this.leftHand.rotation.y = 0.5 * ease;
                    this.leftHand.rotation.x = -0.2 * ease;
                }
                if (this.rightHand) {
                    // Rotate right hand to meet left
                    this.rightHand.rotation.y = -0.5 * ease;
                    this.rightHand.rotation.x = -0.2 * ease;
                }
                
                requestAnimationFrame(animate);
            } else {
                // Hold namaste position briefly, then return
                setTimeout(() => {
                    this.returnFromNamaste(originalLeftArmRot, originalRightArmRot, 
                                          originalLeftHandRot, originalRightHandRot);
                }, 1000); // Hold for 1 second
            }
        };
        
        animate();
    }
    
    returnFromNamaste(originalLeftArmRot, originalRightArmRot, originalLeftHandRot, originalRightHandRot) {
        const startTime = Date.now();
        const duration = 1000;
        
        const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            if (progress < 1) {
                if (this.leftArm && originalLeftArmRot) {
                    this.leftArm.rotation.x = THREE.MathUtils.lerp(-0.5, originalLeftArmRot.x, progress);
                    this.leftArm.rotation.z = THREE.MathUtils.lerp(0.3, originalLeftArmRot.z, progress);
                }
                if (this.rightArm && originalRightArmRot) {
                    this.rightArm.rotation.x = THREE.MathUtils.lerp(-0.5, originalRightArmRot.x, progress);
                    this.rightArm.rotation.z = THREE.MathUtils.lerp(-0.3, originalRightArmRot.z, progress);
                }
                if (this.leftHand && originalLeftHandRot) {
                    this.leftHand.rotation.y = THREE.MathUtils.lerp(0.5, originalLeftHandRot.y, progress);
                    this.leftHand.rotation.x = THREE.MathUtils.lerp(-0.2, originalLeftHandRot.x, progress);
                }
                if (this.rightHand && originalRightHandRot) {
                    this.rightHand.rotation.y = THREE.MathUtils.lerp(-0.5, originalRightHandRot.y, progress);
                    this.rightHand.rotation.x = THREE.MathUtils.lerp(-0.2, originalRightHandRot.x, progress);
                }
                
                requestAnimationFrame(animate);
            }
        };
        
        animate();
    }
    
    stopLipSync() {
        this.isSpeaking = false;
        
        if (this.lipSyncInterval) {
            clearInterval(this.lipSyncInterval);
            this.lipSyncInterval = null;
        }
        
        if (this.audioSource) {
            this.audioSource.disconnect();
            this.audioSource = null;
        }
        
        if (this.mouth) {
            this.mouth.scale.y = 0.7;
            this.mouth.scale.x = 1.4;
        }
        
        this.setEmotion(this.currentEmotion);
    }
    
    startStreamingAnimation() {
        // Stop any existing streaming animation
        this.stopStreamingAnimation();
        
        // Subtle "thinking" animation during streaming
        let frame = 0;
        this.streamingAnimation = setInterval(() => {
            if (!this.avatar) return;
            
            frame++;
            // Subtle head nod or expression change
            if (this.avatar.rotation) {
                // Slight head movement
                this.avatar.rotation.y = Math.sin(frame * 0.1) * 0.05;
            }
            
            // Subtle mouth movement for "speaking" effect
            if (this.mouth) {
                const mouthMovement = 0.7 + Math.sin(frame * 0.2) * 0.15;
                this.mouth.scale.y = mouthMovement;
            }
        }, 50); // Update every 50ms for smooth animation
        
        console.log('🎬 Started streaming animation');
    }
    
    stopStreamingAnimation() {
        if (this.streamingAnimation) {
            clearInterval(this.streamingAnimation);
            this.streamingAnimation = null;
        }
        
        // Reset avatar rotation
        if (this.avatar && this.avatar.rotation) {
            this.avatar.rotation.y = 0;
        }
        
        console.log('🛑 Stopped streaming animation');
    }
    
    reactToToken(token) {
        // React to each token with subtle animation
        // Clear any existing timeout
        if (this.tokenReactionTimeout) {
            clearTimeout(this.tokenReactionTimeout);
        }
        
        // Subtle reaction - slight head movement or expression
        if (this.avatar && this.avatar.rotation) {
            // Quick subtle nod
            const originalY = this.avatar.rotation.y;
            this.avatar.rotation.y = originalY + 0.02;
            
            // Reset after a short time
            this.tokenReactionTimeout = setTimeout(() => {
                if (this.avatar && this.avatar.rotation) {
                    this.avatar.rotation.y = originalY;
                }
            }, 100);
        }
        
        // Subtle mouth movement for each token
        if (this.mouth) {
            const currentScale = this.mouth.scale.y || 0.7;
            this.mouth.scale.y = currentScale + 0.05;
            
            setTimeout(() => {
                if (this.mouth) {
                    this.mouth.scale.y = currentScale;
                }
            }, 50);
        }
    }
    
    handleResize() {
        const canvas = document.getElementById('avatar-canvas');
        if (!canvas || !this.camera || !this.renderer) return;
        
        this.camera.aspect = canvas.clientWidth / canvas.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    }
    
    animate() {
        if (!this.renderer || !this.scene || !this.camera) {
            console.error('Avatar renderer/scene/camera not initialized');
            return;
        }
        
        this.animationFrame = requestAnimationFrame(() => this.animate());
        
        // Render the scene
        this.renderer.render(this.scene, this.camera);
        
        // Elegant breathing animation (only if avatar is loaded)
        if (this.avatar && !this.isSpeaking) {
            // Store base position only once when avatar is first loaded
            if (this._baseAvatarY === undefined) {
                this._baseAvatarY = this.avatar.position.y;
            }
            const breath = Math.sin(Date.now() * 0.001) * 0.015;
            // Add breathing to the stored base position (which includes the lower offset)
            this.avatar.position.y = this._baseAvatarY + breath;
            
            // Keep head facing front with forward tilt (only when not speaking to preserve emotion)
            if (this.head && this.isAwake && !this.isSpeaking) {
                // Maintain forward tilt for face focus (face looking straight)
                if (this._baseHeadTiltX === undefined) {
                    this._baseHeadTiltX = 0.3; // Store the forward tilt value
                }
                this.head.rotation.y = 0; // No side movement
                this.head.rotation.x = this._baseHeadTiltX; // Maintain forward tilt
                this.head.rotation.z = 0; // No tilt to sides
            }
            // During speech, let emotions control head rotation - don't override
            
            // Don't reset avatar rotations - keep model's original orientation
            // Only animate head if needed, but don't force main avatar rotation to 0
        }
        
        // Natural blinking (works during speech too)
        if (this.eyes && this.isAwake && Math.random() < 0.008) {
            this.eyes.left.scale.y = 0.1;
            this.eyes.right.scale.y = 0.1;
            setTimeout(() => {
                if (this.eyes) {
                    this.eyes.left.scale.y = 1.0;
                    this.eyes.right.scale.y = 1.0;
                }
            }, 120);
        }
        
        // Subtle body/hand movements during speech
        if (this.isSpeaking && this.avatar) {
            // Subtle breathing-like movement
            const speechBreath = Math.sin(Date.now() * 0.002) * 0.02;
            if (this._baseAvatarY !== undefined) {
                this.avatar.position.y = this._baseAvatarY + speechBreath;
            }
            
            // Subtle head nod during speech
            if (this.head) {
                const headNod = Math.sin(Date.now() * 0.003) * 0.05;
                this.head.rotation.y += headNod * 0.01; // Very subtle
            }
        }
        
        if (this.mixer) {
            this.mixer.update(0.016);
        }
        
        // Render the scene (after all updates)
        this.renderer.render(this.scene, this.camera);
    }
    
    destroy() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
        if (this.lipSyncInterval) {
            clearInterval(this.lipSyncInterval);
        }
        if (this.audioContext) {
            this.audioContext.close();
        }
        if (this.renderer) {
            this.renderer.dispose();
        }
    }
}
