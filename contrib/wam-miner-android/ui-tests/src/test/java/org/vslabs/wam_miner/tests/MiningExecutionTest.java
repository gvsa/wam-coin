package org.vslabs.wam_miner.tests;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.net.MalformedURLException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.time.Duration;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.json.JSONObject;
import org.openqa.selenium.By;
import org.openqa.selenium.OutputType;
import org.openqa.selenium.TakesScreenshot;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;
import org.testng.Assert;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;
import org.vslabs.wam_miner.utils.LayoutIdParser;

import io.appium.java_client.AppiumBy;
import io.appium.java_client.android.AndroidDriver;
import io.appium.java_client.android.nativekey.AndroidKey;
import io.appium.java_client.android.nativekey.KeyEvent;
import io.appium.java_client.android.options.UiAutomator2Options;

public class MiningExecutionTest {

    private AndroidDriver driver;
    private WebDriverWait wait;
    private Map<String, By> mainLocators;
    private Map<String, By> configLocators;
    private JSONObject testConfig;
    
    @BeforeClass
    public void loadLayouts() {
        mainLocators = LayoutIdParser.parseLayoutIds("activity_main.xml");
        configLocators = LayoutIdParser.parseLayoutIds("activity_config.xml");
        testConfig = loadJsonResource("testprod.json");
    }

    @BeforeMethod
    public void setUp() throws MalformedURLException {
        String apkPath = System.getProperty("apk.path");

        UiAutomator2Options options = new UiAutomator2Options()
                .setPlatformName("Android")
                .setAutomationName("UiAutomator2")
                .setAppPackage("org.vslabs.wam_miner")
                .setAppActivity("org.vslabs.wam_miner.SplashActivity")
                .setAppWaitActivity("org.vslabs.wam_miner.*")
                .setAutoGrantPermissions(true);

        if (apkPath != null && !apkPath.isEmpty()) {
            options.setApp(apkPath);
        }

        driver = new AndroidDriver(URI.create("http://127.0.0.1:4723").toURL(), options);
        wait = new WebDriverWait(driver, Duration.ofSeconds(20));
    }

    @Test(description = "Fill valid config, start mining, wait up to 300s for 2 accepted shares, and capture screenshot")
    public void testStartMiningAndWaitForShares() throws IOException {
        // 1. Navigate from MainActivity to ConfigActivity
        WebElement getStartedBtn = wait.until(ExpectedConditions.elementToBeClickable(mainLocators.get("getStartedBtn")));
        getStartedBtn.click();

        // 2. Read values from testprod.json and populate ConfigActivity fields
        String walletAddress = testConfig.getString("address");
        String stratumUrl = testConfig.getString("stratum");
        String port = String.valueOf(testConfig.get("port"));
        String workerName = testConfig.optString("worker", "appium_test_worker");
        
        WebElement addressInput = wait.until(ExpectedConditions.visibilityOfElementLocated(configLocators.get("input_address")));
        addressInput.clear();
        addressInput.sendKeys(walletAddress);

        WebElement stratumInput = driver.findElement(configLocators.get("input_stratum"));
        stratumInput.clear();
        stratumInput.sendKeys(stratumUrl);

        WebElement portInput = driver.findElement(configLocators.get("input_port"));
        portInput.clear();
        portInput.sendKeys(port);

        WebElement workerInput = driver.findElement(configLocators.get("input_worker"));
        workerInput.clear();
        workerInput.sendKeys(workerName);

        driver.findElement(configLocators.get("coreplus")).click();

        // 3. Save config and allow background ExecutorService thread to populate configObject
        driver.findElement(configLocators.get("saveConfigBtn")).click();
        try {
            Thread.sleep(1500);
        } catch (InterruptedException ignored) {
        }

        driver.findElement(configLocators.get("startnativemining")).click();

        // 4. Verify LogsActivity console TextView renders
        By logConsoleLocator = AppiumBy.className("android.widget.TextView");
        WebElement logTextView = wait.until(ExpectedConditions.visibilityOfElementLocated(logConsoleLocator));
        Assert.assertTrue(logTextView.getText().contains("WAM NATIVE CONSOLE INTERFACE"), "LogsActivity did not initialize");

        // 5. Poll logs for up to 300 seconds until accepted shares >= 2
        WebDriverWait miningWait = new WebDriverWait(driver, Duration.ofSeconds(300));
        miningWait.pollingEvery(Duration.ofSeconds(3));

        boolean reachedTargetShares = miningWait.until(d -> {
            String consoleOutput = d.findElement(logConsoleLocator).getText();
            return countAcceptedShares(consoleOutput) >= 2;
        });

        Assert.assertTrue(reachedTargetShares, "Failed to reach 2 accepted shares within 300 seconds.");

        // 6. Capture screenshot upon reaching 2 accepted shares
        takeScreenshot("accepted_shares_2");
        
        // 7. Press Android Back button, confirm "Stop & Exit", and verify return to ConfigActivity
        driver.pressKey(new KeyEvent(AndroidKey.BACK));

        By stopAndExitBtnLocator = AppiumBy.androidUIAutomator("new UiSelector().textMatches(\"(?i)stop & exit\")");
        WebElement stopAndExitBtn = wait.until(ExpectedConditions.elementToBeClickable(stopAndExitBtnLocator));
        stopAndExitBtn.click();

        WebElement configForm = wait.until(ExpectedConditions.visibilityOfElementLocated(configLocators.get("form")));
        Assert.assertTrue(configForm.isDisplayed(), "Did not return to ConfigActivity after stopping miner");
    }
    /**
     * Parses console log text for accepted shares (supports counters like "accepted: 2/2" or individual lines).
     */
    private int countAcceptedShares(String logText) {
        if (logText == null || logText.isEmpty()) {
            return 0;
        }
        String lowerText = logText.toLowerCase();

        Matcher counterMatcher = Pattern.compile("accepted[:\\s\\(]+(\\d+)").matcher(lowerText);
        int maxCounter = 0;
        while (counterMatcher.find()) {
            int val = Integer.parseInt(counterMatcher.group(1));
            if (val > maxCounter) {
                maxCounter = val;
            }
        }
        if (maxCounter >= 2) {
            return maxCounter;
        }

        Matcher lineMatcher = Pattern.compile("\\baccepted\\b").matcher(lowerText);
        int occurrences = 0;
        while (lineMatcher.find()) {
            occurrences++;
        }
        return occurrences;
    }

    private void takeScreenshot(String fileNamePrefix) throws IOException {
        File srcFile = ((TakesScreenshot) driver).getScreenshotAs(OutputType.FILE);
        Path targetDir = Paths.get("target", "screenshots");
        Files.createDirectories(targetDir);
        Path destination = targetDir.resolve(fileNamePrefix + "_" + System.currentTimeMillis() + ".png");
        Files.copy(srcFile.toPath(), destination, StandardCopyOption.REPLACE_EXISTING);
        System.out.println("Saved screenshot to: " + destination.toAbsolutePath());
    }
    
    private JSONObject loadJsonResource(String fileName) {
        try (InputStream is = getClass().getClassLoader().getResourceAsStream(fileName)) {
            if (is == null) {
                throw new RuntimeException("Resource file not found in src/test/resources: " + fileName);
            }
            String content = new String(is.readAllBytes(), StandardCharsets.UTF_8);
            return new JSONObject(content);
        } catch (IOException e) {
            throw new RuntimeException("Failed to read JSON resource: " + fileName, e);
        }
    }
    

    @AfterMethod(alwaysRun = true)
    public void tearDown() {
        if (driver != null) {
            driver.quit();
        }
    }
    
    
}
