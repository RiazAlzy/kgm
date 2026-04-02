document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById('graph-container');
    let breadcrumbs = [];

    const Graph = ForceGraph()(container)
        .backgroundColor('#f8fafc')
        .nodeId('id')
        // NODE RENDERING
        .nodeCanvasObject((node, ctx, globalScale) => {
            const label = node.name || '';
            const fontSize = 14;
            ctx.font = `500 ${fontSize}px Inter, sans-serif`;
            
            // Calculate radius dynamically to fit the text
            const textWidth = ctx.measureText(label).width;
            const radius = Math.max(textWidth / 2 + 12, 20);
            node.__radius = radius;

            ctx.beginPath();
            ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
            
            // Thematic coloring based on state
            if (node.group === 'current') {
                ctx.fillStyle = '#2563eb';
                ctx.lineWidth = 3 / globalScale;
                ctx.strokeStyle = '#bfdbfe';
            } else if (node.group === 'breadcrumb') {
                ctx.fillStyle = '#64748b';
                ctx.lineWidth = 2 / globalScale;
                ctx.strokeStyle = '#e2e8f0';
            } else {
                ctx.fillStyle = '#10b981';
                ctx.lineWidth = 2 / globalScale;
                ctx.strokeStyle = '#d1fae5';
            }
            
            ctx.fill();
            ctx.stroke();

            // Render text dead center inside the colored circle
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#ffffff';
            ctx.fillText(label, node.x, node.y);
        })
        // ENSURE HOVER & CLICK HITBOX MATCHES CUSTOM NODE SIZE
        .nodePointerAreaPaint((node, color, ctx) => {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.__radius || 20, 0, 2 * Math.PI, false);
            ctx.fill();
        })
        .linkColor(() => '#94a3b8')
        .linkWidth(2)
        .linkDirectionalArrowLength(6)
        .linkDirectionalArrowRelPos(0.65)
        .linkCurvature(0)
        // RELATION TEXT ON LINES
        .linkCanvasObjectMode(() => 'after')
        .linkCanvasObject((link, ctx) => {
            const LABEL = link.relation;
            if (!LABEL) return;

            const start = link.source;
            const end = link.target;
            if (typeof start !== 'object' || typeof end !== 'object') return;

            const textPos = {
                x: start.x + (end.x - start.x) / 2,
                y: start.y + (end.y - start.y) / 2
            };

            const relLink = { x: end.x - start.x, y: end.y - start.y };
            let textAngle = Math.atan2(relLink.y, relLink.x);
            if (textAngle > Math.PI / 2) textAngle = -(Math.PI - textAngle);
            if (textAngle < -Math.PI / 2) textAngle = -(-Math.PI - textAngle);

            const fontSize = 11;
            ctx.font = `500 ${fontSize}px Inter, sans-serif`;
            
            const textWidth = ctx.measureText(LABEL).width;
            const bckgDimensions = [textWidth + 8, fontSize + 6]; 
            
            ctx.save();
            ctx.translate(textPos.x, textPos.y);
            ctx.rotate(textAngle);
            
            // Background label box masking out the line beneath it
            ctx.fillStyle = '#f8fafc';
            ctx.fillRect(-bckgDimensions[0] / 2, -bckgDimensions[1] / 2, bckgDimensions[0], bckgDimensions[1]);

            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#475569';
            ctx.fillText(LABEL, 0, 0);
            ctx.restore();
        })
        .onNodeClick(handleNodeClick)
        .onNodeRightClick(handleNodeRightClick);
        
    Graph.d3Force('charge').strength(-1000); 
    Graph.d3Force('link').distance(80);

    fetchGraphData(null);

    async function fetchGraphData(nodeId) {
        const url = new URL('/graph/api/expand/', window.location.origin);
        if (nodeId) {
            url.searchParams.append('node_id', nodeId);
            // Array continues to route under the hood for API state pruning
            url.searchParams.append('breadcrumbs', JSON.stringify(breadcrumbs));
        }

        try {
            const response = await fetch(url);
            const data = await response.json();
            
            const currentData = Graph.graphData();
            if (currentData.nodes.length > 0) {
                data.nodes.forEach(newNode => {
                    const existingNode = currentData.nodes.find(n => n.id === newNode.id);
                    if (existingNode) {
                        newNode.x = existingNode.x;
                        newNode.y = existingNode.y;
                        newNode.vx = existingNode.vx;
                        newNode.vy = existingNode.vy;
                    }
                });
            }

            Graph.graphData(data);

            if (!nodeId) {
                setTimeout(() => {
                    Graph.zoomToFit(400, 50);
                }, 800);
            }
            
        } catch (error) {
            console.error("Graph Traversal Error:", error);
        }
    }

    function handleNodeClick(node) {
        const index = breadcrumbs.indexOf(node.id);
        
        if (index !== -1) {
            breadcrumbs = breadcrumbs.slice(0, index + 1);
        } else {
            const { links } = Graph.graphData();
            let highestConnectedIndex = -1;
            
            for (let i = breadcrumbs.length - 1; i >= 0; i--) {
                const bcNodeId = breadcrumbs[i];
                const isConnected = links.some(l => 
                    (l.source.id === node.id && l.target.id === bcNodeId) ||
                    (l.target.id === node.id && l.source.id === bcNodeId)
                );
                
                if (isConnected) {
                    highestConnectedIndex = i;
                    break; 
                }
            }

            if (highestConnectedIndex !== -1) {
                breadcrumbs = breadcrumbs.slice(0, highestConnectedIndex + 1);
                breadcrumbs.push(node.id);
            } else {
                breadcrumbs = [node.id];
            }
        }

        Graph.centerAt(node.x, node.y, 1000);
        Graph.zoom(3, 2000);
        
        fetchGraphData(node.id);
    }

    function handleNodeRightClick(node) {
        if (!node.asset_ids || node.asset_ids.length === 0) return;
        const idsParam = node.asset_ids.join(',');
        htmx.ajax('GET', `/graph/api/asset/${idsParam}/`, {
            target: '#modal-container', 
            swap: 'innerHTML'
        });
    }

    window.addEventListener('resize', () => {
        Graph.width(container.clientWidth);
        Graph.height(container.clientHeight);
    });
});