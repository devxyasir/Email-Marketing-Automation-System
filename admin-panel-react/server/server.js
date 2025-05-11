const express = require('express');
const cors = require('cors');
const { MongoClient, ObjectId } = require('mongodb');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 5000;

// MongoDB connection string
const MONGODB_URI = process.env.MONGODB_URI || "mongodb+srv://JHpRv89n2ml6gxns:JHpRv89n2ml6gxns@cluster0.e9lk1.mongodb.net/";
const MONGODB_DB = process.env.MONGODB_DB || "email_automation";

// Middleware
app.use(cors());
app.use(express.json());

// MongoDB Connection
let db;

async function connectToMongoDB() {
  try {
    const client = await MongoClient.connect(MONGODB_URI);
    db = client.db(MONGODB_DB);
    console.log('Connected to MongoDB');
  } catch (error) {
    console.error('MongoDB connection error:', error);
    process.exit(1);
  }
}

// Collection names
const COLLECTIONS = {
  LICENSES: 'licenses',
  EMAIL_CONFIG: 'email_config',
  USERS: 'users',
  ACTIVITY_LOGS: 'activity_logs',
  SETTINGS: 'settings'
};

// API Routes

// === Users API ===
// Get all users
app.get('/api/users', async (req, res) => {
  try {
    const users = await db.collection(COLLECTIONS.LICENSES)
      .find({})
      .project({ _id: 1, License_Code: 1, registered_system_id: 1, expiryDate: 1, activationDate: 1 })
      .toArray();
      
    res.json(users);
  } catch (error) {
    console.error('Error fetching users:', error);
    res.status(500).json({ error: 'Error fetching users' });
  }
});

// Get user by ID
app.get('/api/users/:id', async (req, res) => {
  try {
    const user = await db.collection(COLLECTIONS.LICENSES).findOne({ _id: new ObjectId(req.params.id) });
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    res.json(user);
  } catch (error) {
    console.error('Error fetching user:', error);
    res.status(500).json({ error: 'Error fetching user' });
  }
});

// Create new user/license
app.post('/api/users', async (req, res) => {
  try {
    const { licenseCode, expiryDays } = req.body;
    
    if (!licenseCode) {
      return res.status(400).json({ error: 'License code is required' });
    }
    
    // Check if license already exists
    const existingLicense = await db.collection(COLLECTIONS.LICENSES).findOne({ License_Code: licenseCode });
    if (existingLicense) {
      return res.status(400).json({ error: 'License code already exists' });
    }
    
    // Calculate expiry date if provided
    let expiryDate = null;
    let timeFrame = 'unlimited';
    
    if (expiryDays && expiryDays > 0) {
      expiryDate = new Date();
      expiryDate.setDate(expiryDate.getDate() + parseInt(expiryDays));
      timeFrame = `${expiryDays} days`;
    }
    
    // Create new license
    const newLicense = {
      License_Code: licenseCode,
      registered_system_id: null,
      expiryDate: expiryDate,
      createdAt: new Date(),
      timeFrame: timeFrame
    };
    
    const result = await db.collection(COLLECTIONS.LICENSES).insertOne(newLicense);
    res.status(201).json({ 
      _id: result.insertedId,
      ...newLicense 
    });
  } catch (error) {
    console.error('Error creating user/license:', error);
    res.status(500).json({ error: 'Error creating user/license' });
  }
});

// Update user/license
app.put('/api/users/:id', async (req, res) => {
  try {
    const { licenseCode, expiryDays } = req.body;
    const updateData = {};
    
    if (licenseCode) updateData.License_Code = licenseCode;
    
    // Update expiry date if provided
    if (expiryDays) {
      const expiryDate = new Date();
      expiryDate.setDate(expiryDate.getDate() + parseInt(expiryDays));
      updateData.expiryDate = expiryDate;
      updateData.timeFrame = `${expiryDays} days`;
    }
    
    updateData.updatedAt = new Date();
    
    const result = await db.collection(COLLECTIONS.LICENSES).updateOne(
      { _id: new ObjectId(req.params.id) },
      { $set: updateData }
    );
    
    if (result.matchedCount === 0) {
      return res.status(404).json({ error: 'User/license not found' });
    }
    
    res.json({ message: 'User/license updated successfully' });
  } catch (error) {
    console.error('Error updating user/license:', error);
    res.status(500).json({ error: 'Error updating user/license' });
  }
});

// Delete user/license
app.delete('/api/users/:id', async (req, res) => {
  try {
    const result = await db.collection(COLLECTIONS.LICENSES).deleteOne({ _id: new ObjectId(req.params.id) });
    
    if (result.deletedCount === 0) {
      return res.status(404).json({ error: 'User/license not found' });
    }
    
    res.json({ message: 'User/license deleted successfully' });
  } catch (error) {
    console.error('Error deleting user/license:', error);
    res.status(500).json({ error: 'Error deleting user/license' });
  }
});

// === Email Configurations API ===
// Get all email configurations
app.get('/api/email-configs', async (req, res) => {
  try {
    // First check the email_config collection (older records)
    let emailConfigs = await db.collection(COLLECTIONS.EMAIL_CONFIG).find({}).toArray();
    
    // Then check the settings collection for smtp records (newer records)
    const smtpConfigs = await db.collection(COLLECTIONS.SETTINGS)
      .find({ setting_type: "smtp" })
      .toArray();
    
    // Combine the results, prioritizing newer settings
    if (smtpConfigs && smtpConfigs.length > 0) {
      // Add to the email configs list, but format for consistent display
      smtpConfigs.forEach(config => {
        // Push each configuration with needed fields mapped
        emailConfigs.push({
          _id: config._id,
          hardware_id: config.hardware_id,
          email: config.email || 'N/A',
          password: config.password || 'N/A',
          smtp_server: config.smtp_server || 'N/A',
          smtp_port: config.smtp_port || 'N/A',
          provider: config.provider || 'Unknown',
          updated_at: config.updated_at || new Date(),
          setting_type: config.setting_type,
          source: 'settings_collection'
        });
      });
    }
    
    console.log(`Found ${emailConfigs.length} email configurations`);
    
    res.json(emailConfigs);
  } catch (error) {
    console.error('Error fetching email configurations:', error);
    res.status(500).json({ error: 'Error fetching email configurations' });
  }
});

// Get email configuration by hardware ID
app.get('/api/email-configs/:hardwareId', async (req, res) => {
  try {
    // First try to find in settings collection
    let emailConfig = await db.collection(COLLECTIONS.SETTINGS).findOne({ 
      hardware_id: req.params.hardwareId,
      setting_type: "smtp"
    });
    
    // If not found, check the email_config collection
    if (!emailConfig) {
      emailConfig = await db.collection(COLLECTIONS.EMAIL_CONFIG).findOne({ 
        hardware_id: req.params.hardwareId 
      });
    }
    
    if (!emailConfig) {
      return res.status(404).json({ error: 'Email configuration not found' });
    }
    
    res.json(emailConfig);
  } catch (error) {
    console.error('Error fetching email configuration:', error);
    res.status(500).json({ error: 'Error fetching email configuration' });
  }
});

// Delete email configuration
app.delete('/api/email-configs/:id', async (req, res) => {
  try {
    const result = await db.collection(COLLECTIONS.EMAIL_CONFIG).deleteOne({ 
      _id: new ObjectId(req.params.id) 
    });
    
    if (result.deletedCount === 0) {
      return res.status(404).json({ error: 'Email configuration not found' });
    }
    
    res.json({ message: 'Email configuration deleted successfully' });
  } catch (error) {
    console.error('Error deleting email configuration:', error);
    res.status(500).json({ error: 'Error deleting email configuration' });
  }
});

// === Dashboard Stats API ===
// Get dashboard statistics
app.get('/api/stats', async (req, res) => {
  try {
    const totalUsers = await db.collection(COLLECTIONS.LICENSES).countDocuments();
    const registeredUsers = await db.collection(COLLECTIONS.LICENSES).countDocuments({ 
      registered_system_id: { $ne: null }
    });
    const emailConfigs = await db.collection(COLLECTIONS.EMAIL_CONFIG).countDocuments();
    
    // Get expiring soon licenses (within 7 days)
    const sevenDaysFromNow = new Date();
    sevenDaysFromNow.setDate(sevenDaysFromNow.getDate() + 7);
    
    const expiringSoon = await db.collection(COLLECTIONS.LICENSES).countDocuments({
      expiryDate: { 
        $exists: true, 
        $ne: null,
        $gt: new Date(),
        $lt: sevenDaysFromNow
      }
    });
    
    res.json({
      totalUsers,
      registeredUsers,
      emailConfigs,
      expiringSoon
    });
  } catch (error) {
    console.error('Error fetching stats:', error);
    res.status(500).json({ error: 'Error fetching stats' });
  }
});

// Start server
app.listen(PORT, async () => {
  await connectToMongoDB();
  console.log(`Server running on port ${PORT}`);
});
