#(©)CodeXBotz




import pymongo, os
from config import DB_URI, DB_NAME


dbclient = pymongo.MongoClient(DB_URI)
database = dbclient[DB_NAME]


user_data = database['users']
fsub = database['fsub']
referrals_collection = database['referrals']
user_tokens_collection = database['user_tokens']
referral_transactions_collection = database['referral_transactions']



async def present_user(user_id : int):
    found = user_data.find_one({'_id': user_id})
    return bool(found)

async def add_user(user_id: int):
    user_data.insert_one({'_id': user_id})
    return

async def full_userbase():
    user_docs = user_data.find()
    user_ids = []
    for doc in user_docs:
        user_ids.append(doc['_id'])
        
    return user_ids

async def del_user(user_id: int):
    user_data.delete_one({'_id': user_id})
    return

async def add_referral_user(referrer_id: int, referred_id: int):
    """Add a new referral record"""
    try:
        # Check if this referral already exists
        existing = referrals_collection.find_one({
            "referrer_id": referrer_id,
            "referred_id": referred_id
        })
        
        if existing:
            return False  # Already referred
        
        # Add referral record
        referral_data = {
            "referrer_id": referrer_id,
            "referred_id": referred_id,
            "timestamp": datetime.utcnow(),
            "tokens_awarded": True
        }
        
        referrals_collection.insert_one(referral_data)
        
        # Initialize token balance for new user if not exists
        if not user_tokens_collection.find_one({"user_id": referred_id}):
            user_tokens_collection.insert_one({
                "user_id": referred_id,
                "tokens": 0,
                "total_earned": 0,
                "total_sold": 0,
                "created_at": datetime.utcnow()
            })
        
        return True
        
    except Exception as e:
        print(f"Error in add_referral_user: {e}")
        return False

async def get_user_tokens(user_id: int):
    """Get user's current token balance"""
    try:
        user_data = user_tokens_collection.find_one({"user_id": user_id})
        if user_data:
            return user_data.get("tokens", 0)
        else:
            # Create user record if doesn't exist
            user_tokens_collection.insert_one({
                "user_id": user_id,
                "tokens": 0,
                "total_earned": 0,
                "total_sold": 0,
                "created_at": datetime.utcnow()
            })
            return 0
    except Exception as e:
        print(f"Error in get_user_tokens: {e}")
        return 0

async def update_user_tokens(user_id: int, token_change: int):
    """Update user's token balance (positive to add, negative to deduct)"""
    try:
        user_data = user_tokens_collection.find_one({"user_id": user_id})
        
        if not user_data:
            # Create user record if doesn't exist
            initial_tokens = max(0, token_change)  # Don't allow negative starting balance
            user_tokens_collection.insert_one({
                "user_id": user_id,
                "tokens": initial_tokens,
                "total_earned": initial_tokens if token_change > 0 else 0,
                "total_sold": 0,
                "created_at": datetime.utcnow()
            })
            return initial_tokens
        
        # Update tokens
        current_tokens = user_data.get("tokens", 0)
        new_balance = max(0, current_tokens + token_change)  # Don't allow negative balance
        
        update_data = {"tokens": new_balance}
        
        # Update total earned/sold counters
        if token_change > 0:
            update_data["total_earned"] = user_data.get("total_earned", 0) + token_change
        elif token_change < 0:
            update_data["total_sold"] = user_data.get("total_sold", 0) + abs(token_change)
        
        user_tokens_collection.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
        
        return new_balance
        
    except Exception as e:
        print(f"Error in update_user_tokens: {e}")
        return 0

async def get_referral_stats(user_id: int):
    """Get detailed referral statistics for a user"""
    try:
        # Count total referrals
        total_referrals = referrals_collection.count_documents({"referrer_id": user_id})
        
        # Get user token data
        user_data = user_tokens_collection.find_one({"user_id": user_id})
        
        if not user_data:
            return {
                "total_referrals": total_referrals,
                "total_tokens_earned": 0,
                "tokens_sold": 0,
                "total_earnings": 0.0
            }
        
        total_tokens_earned = user_data.get("total_earned", 0)
        tokens_sold = user_data.get("total_sold", 0)
        
        # Calculate total earnings from transactions
        total_earnings = 0.0
        transactions = referral_transactions_collection.find({
            "user_id": user_id,
