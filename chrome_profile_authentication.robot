*** Settings ***
Library    Browser
Library    OperatingSystem

*** Variables ***
${PROFILE_DIR}    C:\\temp\\SelfOperatingComputer_Profile

*** Test Cases ***
Production Software Flow
    [Documentation]    Demonstrates complete production flow for self-operating computer software
    [Tags]    production    software    flow
    
    Log    🚀 SELF-OPERATING COMPUTER - PRODUCTION FLOW    console=True
    Log    ═══════════════════════════════════════════════    console=True
    
    # STEP 1: Software Startup - Check Authentication
    Log    📋 STEP 1: Checking authentication status...    console=True
    ${auth_status}=    Check Authentication Status
    
    IF    "${auth_status}" == "AUTHENTICATED"
        Log    ✅ User authenticated - proceeding with automation    console=True
        Log    🎯 Ready to execute Google services tasks    console=True
        
        # Your software would continue here with normal operation
        Demo Authenticated Operation
        
    ELSE IF    "${auth_status}" == "FIRST_TIME"
        Log    🔑 FIRST-TIME USER DETECTED    console=True
        Log    ═══════════════════════════════════════════════    console=True
        Log    📢 WELCOME TO SELF-OPERATING COMPUTER!    console=True
        Log    📋 Initial setup required for Google services    console=True
        Log    ⚠️ This is a ONE-TIME setup process    console=True
        
        ${setup_completed}=    Prompt Initial Setup
        
        IF    ${setup_completed}
            Log    ✅ Setup complete! Software ready for use.    console=True
            Demo Authenticated Operation
        ELSE
            Log    ❌ Setup was cancelled or incomplete    console=True
            Log    💡 Google services will not be available    console=True
            Log    🔄 You can run setup again anytime    console=True
            # Software could continue with limited functionality
        END
        
    ELSE IF    "${auth_status}" == "EXPIRED"
        Log    ⚠️ AUTHENTICATION EXPIRED    console=True
        Log    ═══════════════════════════════════════════════    console=True
        Log    🔄 Your Google authentication has expired    console=True
        Log    📋 Please re-authenticate to continue    console=True
        
        ${reauth_completed}=    Prompt Reauthentication
        
        IF    ${reauth_completed}
            Log    ✅ Re-authentication complete!    console=True
            Demo Authenticated Operation
        ELSE
            Log    ❌ Re-authentication failed    console=True
            Log    💡 Some features may be unavailable    console=True
        END
        
    ELSE
        Log    ❌ Unknown authentication status    console=True
        Log    🔧 Please contact support    console=True
    END
    
    Log    ═══════════════════════════════════════════════    console=True
    Log    ✅ Self-Operating Computer session complete    console=True

*** Keywords ***
Check Authentication Status
    [Documentation]    Determines the current authentication status for the application
    
    Log    🔍 Checking Google authentication status...    console=True
    
    # Check if profile directory exists
    ${profile_exists}=    Run Keyword And Return Status    Directory Should Exist    ${PROFILE_DIR}
    
    IF    not ${profile_exists}
        Log    📁 No profile found - first-time user    console=True
        RETURN    FIRST_TIME
    END
    
    # Check if authenticated by testing Gmail access
    TRY
        New Persistent Context    userDataDir=${PROFILE_DIR}    headless=True
        ...    args=["--disable-blink-features=AutomationControlled", "--disable-extensions", "--no-first-run", "--password-store=basic"]
        
        New Page    https://gmail.com
        Sleep    5s
        
        ${title}=    Get Title
        Close Browser
        
        # Determine authentication status
        ${has_inbox}=    Evaluate    "inbox" in "${title}".lower()
        ${has_email}=    Evaluate    "@gmail.com" in "${title}".lower() or "@googlemail.com" in "${title}".lower()
        ${needs_signin}=    Evaluate    "sign in" in "${title}".lower()
        
        IF    ${has_inbox} or ${has_email}
            Log    ✅ Valid authentication found    console=True
            RETURN    AUTHENTICATED
        ELSE IF    ${needs_signin}
            Log    ⚠️ Authentication expired or invalid    console=True
            RETURN    EXPIRED
        ELSE
            Log    🔑 No valid authentication    console=True
            RETURN    FIRST_TIME
        END
        
    EXCEPT
        Log    ❌ Auth check failed - treating as first time    console=True
        TRY
            Close Browser
        EXCEPT
            Log    Browser cleanup    console=True
        END
        RETURN    FIRST_TIME
    END

Prompt Initial Setup
    [Documentation]    Prompts user for initial Google authentication setup
    
    Log    🎯 INITIAL SETUP: Google Authentication    console=True
    Log    ═══════════════════════════════════════════════    console=True
    Log    📢 Why do we need Google authentication?    console=True
    Log    • Access Gmail for email automation    console=True
    Log    • Use Google Drive for file operations    console=True
    Log    • Integrate with Google Calendar    console=True
    Log    • Enable Google Search automation    console=True
    Log    ═══════════════════════════════════════════════    console=True
    Log    📋 SETUP PROCESS:    console=True
    Log    1. Chrome browser will open to Google sign-in    console=True
    Log    2. Sign in with your Google account    console=True
    Log    3. System will automatically detect completion    console=True
    Log    4. Your credentials will be securely saved    console=True
    Log    ⏳ Maximum setup time: 5 minutes    console=True
    Log    ═══════════════════════════════════════════════    console=True
    
    # Create profile directory
    Create Directory    ${PROFILE_DIR}
    
    # Launch setup browser
    New Persistent Context    userDataDir=${PROFILE_DIR}    headless=False
    ...    args=["--disable-blink-features=AutomationControlled", "--disable-extensions", "--no-first-run", "--password-store=basic"]
    
    New Page    https://accounts.google.com/signin
    Sleep    3s
    
    Log    🔓 Google sign-in opened - please complete authentication    console=True
    
    # Monitor setup progress
    ${setup_success}=    Monitor Setup Progress    max_minutes=5
    
    Close Browser
    
    IF    ${setup_success}
        Log    🎉 Setup successful! Testing authentication...    console=True
        Sleep    3s
        
        # Verify setup worked
        ${auth_status}=    Check Authentication Status
        ${verified}=    Evaluate    "${auth_status}" == "AUTHENTICATED"
        
        IF    ${verified}
            Log    ✅ Authentication verified! Setup complete.    console=True
            RETURN    True
        ELSE
            Log    ⚠️ Setup verification failed - please try again    console=True
            RETURN    False
        END
    ELSE
        Log    ❌ Setup was not completed within time limit    console=True
        RETURN    False
    END

Prompt Reauthentication
    [Documentation]    Prompts user to re-authenticate when auth has expired
    
    Log    🔄 RE-AUTHENTICATION REQUIRED    console=True
    Log    ═══════════════════════════════════════════════    console=True
    Log    📢 Your Google authentication has expired    console=True
    Log    🔒 This happens periodically for security    console=True
    Log    📋 Please sign in again to continue    console=True
    Log    ═══════════════════════════════════════════════    console=True
    
    # Use existing profile for re-auth
    New Persistent Context    userDataDir=${PROFILE_DIR}    headless=False
    ...    args=["--disable-blink-features=AutomationControlled", "--disable-extensions", "--no-first-run", "--password-store=basic"]
    
    New Page    https://accounts.google.com/signin
    Sleep    2s
    
    Log    🔓 Please re-authenticate in the browser window    console=True
    
    ${reauth_success}=    Monitor Setup Progress    max_minutes=3
    
    Close Browser
    
    RETURN    ${reauth_success}

Monitor Setup Progress
    [Documentation]    Monitors authentication setup/re-auth progress
    [Arguments]    ${max_minutes}=5
    
    ${max_checks}=    Evaluate    ${max_minutes} * 6    # Check every 10 seconds
    
    Log    🔍 Monitoring authentication progress...    console=True
    
    FOR    ${check}    IN RANGE    ${max_checks}
        Sleep    10s
        
        TRY
            ${title}=    Get Title
            ${url}=    Get Url
            
            # Progress updates
            ${minute_check}=    Evaluate    ${check} % 6
            IF    ${minute_check} == 0 and ${check} > 0
                ${elapsed}=    Evaluate    round(${check} / 6, 1)
                Log    ⏳ ${elapsed} minutes - still monitoring...    console=True
            END
            
            # Check for completion
            ${completed}=    Is Authentication Complete    ${title}    ${url}
            
            IF    ${completed}
                ${elapsed}=    Evaluate    round(${check} / 6, 1)
                Log    🎉 Authentication completed after ${elapsed} minutes!    console=True
                RETURN    True
            END
            
        EXCEPT
            Log    🔍 Continuing to monitor...    console=True
        END
    END
    
    Log    ⏰ Authentication timeout - setup incomplete    console=True
    RETURN    False

Is Authentication Complete
    [Documentation]    Checks if authentication is complete based on page indicators
    [Arguments]    ${title}    ${url}
    
    # Skip sign-in pages
    ${signin_keywords}=    Create List    sign in    signin    choose an account    choose account
    FOR    ${keyword}    IN    @{signin_keywords}
        ${is_signin_page}=    Evaluate    "${keyword}" in "${title}".lower()
        IF    ${is_signin_page}
            RETURN    False
        END
    END
    
    # Check for success indicators
    ${success_keywords}=    Create List    google account    my account    inbox    gmail    @gmail.com    myaccount.google.com    mail.google.com    drive.google.com
    FOR    ${keyword}    IN    @{success_keywords}
        ${has_success}=    Evaluate    "${keyword}" in "${title}".lower() or "${keyword}" in "${url}".lower()
        IF    ${has_success}
            RETURN    True
        END
    END
    
    RETURN    False

Demo Authenticated Operation
    [Documentation]    Demonstrates what happens when user is authenticated
    
    Log    🎯 AUTHENTICATED OPERATION DEMO    console=True
    Log    ═══════════════════════════════════════════════    console=True
    Log    ✅ Google services are available:    console=True
    Log    📧 Gmail automation - READY    console=True
    Log    💾 Google Drive access - READY    console=True
    Log    📅 Google Calendar integration - READY    console=True
    Log    🔍 Google Search automation - READY    console=True
    Log    ═══════════════════════════════════════════════    console=True
    
    # Quick demo of authenticated access
    Log    📧 Testing Gmail access...    console=True
    
    New Persistent Context    userDataDir=${PROFILE_DIR}    headless=True
    ...    args=["--disable-blink-features=AutomationControlled", "--disable-extensions", "--no-first-run", "--password-store=basic"]
    
    New Page    https://gmail.com
    Sleep    3s
    
    ${gmail_title}=    Get Title
    Close Browser
    
    Log    📧 Gmail status: ${gmail_title}    console=True
    Log    🎉 Self-Operating Computer is ready for automation!    console=True 