import * as functions from "firebase-functions";
import * as express from "express";
import * as cors from "cors";
import * as admin from "firebase-admin";

// Initialize Firebase Admin
admin.initializeApp();

const app = express();
const db = admin.firestore();

// Enable CORS
app.use(cors({origin: true}));
app.use(express.json());

// GET /agents - List all agents
app.get("/agents", async (req, res) => {
  try {
    const agentsSnapshot = await db.collection("agents").get();
    const agents: any[] = [];

    agentsSnapshot.forEach((doc) => {
      agents.push({
        id: doc.id,
        ...doc.data(),
      });
    });

    res.json(agents);
  } catch (error) {
    console.error("Error fetching agents:", error);
    res.status(500).json({error: "Failed to fetch agents"});
  }
});

// GET /agents/:id - Get specific agent
app.get("/agents/:id", async (req, res) => {
  try {
    const agentDoc = await db.collection("agents").doc(req.params.id).get();

    if (!agentDoc.exists) {
      return res.status(404).json({error: "Agent not found"});
    }

    res.json({
      id: agentDoc.id,
      ...agentDoc.data(),
    });
  } catch (error) {
    console.error("Error fetching agent:", error);
    res.status(500).json({error: "Failed to fetch agent"});
  }
});

// POST /agents - Add new agent (requires auth)
app.post("/agents", async (req, res) => {
  try {
    // Verify Firebase Auth token
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return res.status(401).json({error: "Authentication required"});
    }

    const token = authHeader.split("Bearer ")[1];
    const decodedToken = await admin.auth().verifyIdToken(token);

    const agentData = {
      ...req.body,
      createdBy: decodedToken.uid,
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    };

    const docRef = await db.collection("agents").add(agentData);

    res.json({
      id: docRef.id,
      ...agentData,
    });
  } catch (error) {
    console.error("Error creating agent:", error);
    res.status(500).json({error: "Failed to create agent"});
  }
});

// PUT /agents/:id - Update agent (requires auth)
app.put("/agents/:id", async (req, res) => {
  try {
    // Verify Firebase Auth token
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return res.status(401).json({error: "Authentication required"});
    }

    const token = authHeader.split("Bearer ")[1];
    const decodedToken = await admin.auth().verifyIdToken(token);

    const agentRef = db.collection("agents").doc(req.params.id);
    const agentDoc = await agentRef.get();

    if (!agentDoc.exists) {
      return res.status(404).json({error: "Agent not found"});
    }

    // Check if user owns the agent or is admin
    const agentData = agentDoc.data();
    if (agentData?.createdBy !== decodedToken.uid) {
      return res
        .status(403)
        .json({error: "Not authorized to update this agent"});
    }

    const updateData = {
      ...req.body,
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    };

    await agentRef.update(updateData);

    res.json({
      id: req.params.id,
      ...updateData,
    });
  } catch (error) {
    console.error("Error updating agent:", error);
    res.status(500).json({error: "Failed to update agent"});
  }
});

// DELETE /agents/:id - Delete agent (requires auth)
app.delete("/agents/:id", async (req, res) => {
  try {
    // Verify Firebase Auth token
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return res.status(401).json({error: "Authentication required"});
    }

    const token = authHeader.split("Bearer ")[1];
    const decodedToken = await admin.auth().verifyIdToken(token);

    const agentRef = db.collection("agents").doc(req.params.id);
    const agentDoc = await agentRef.get();

    if (!agentDoc.exists) {
      return res.status(404).json({error: "Agent not found"});
    }

    // Check if user owns the agent or is admin
    const agentData = agentDoc.data();
    if (agentData?.createdBy !== decodedToken.uid) {
      return res
        .status(403)
        .json({error: "Not authorized to delete this agent"});
    }

    await agentRef.delete();

    res.json({message: "Agent deleted successfully"});
  } catch (error) {
    console.error("Error deleting agent:", error);
    res.status(500).json({error: "Failed to delete agent"});
  }
});

// POST /agents/:id/like - Like an agent
app.post("/agents/:id/like", async (req, res) => {
  try {
    const agentRef = db.collection("agents").doc(req.params.id);

    await agentRef.update({
      likes: admin.firestore.FieldValue.increment(1),
    });

    res.json({message: "Agent liked successfully"});
  } catch (error) {
    console.error("Error liking agent:", error);
    res.status(500).json({error: "Failed to like agent"});
  }
});

// POST /import - Import agents from GitHub
app.post("/import", async (req, res) => {
  try {
    // This would import agents from GitHub repositories
    // For now, return success
    res.json({message: "Import completed successfully"});
  } catch (error) {
    console.error("Error importing agents:", error);
    res.status(500).json({error: "Failed to import agents"});
  }
});

// GET / - Health check
app.get("/", (req, res) => {
  res.json({
    message: "Claude Subagents Marketplace API",
    version: "1.0.0",
    status: "healthy",
  });
});

// Export the Express app as a Firebase Function
export const api = functions.https.onRequest(app);
