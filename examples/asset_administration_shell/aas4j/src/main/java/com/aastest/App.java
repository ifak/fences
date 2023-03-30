package com.aastest;

import org.eclipse.digitaltwin.aas4j.v3.dataformat.DeserializationException;
import org.eclipse.digitaltwin.aas4j.v3.dataformat.SerializationException;
import org.eclipse.digitaltwin.aas4j.v3.dataformat.json.JsonDeserializer;
import org.eclipse.digitaltwin.aas4j.v3.dataformat.json.JsonSerializer;
import org.eclipse.digitaltwin.aas4j.v3.model.Environment;

import org.json.JSONObject;


import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.io.PrintWriter;
import java.io.StringWriter;

public class App {
    static JSONObject evaluationResults = new JSONObject();

   static int E_NO_ERROR = 0;
   static int E_INPUT_ERROR = 1;
   static int E_DESERIALIZATION_ERROR = 2;
   static int E_VALIDATION_ERROR = 3;
   static int E_SERIALIZATION_ERROR = 4;
   static int E_OUTPUT_ERROR = 5;


    private static JSONObject run_test(File file) {
        JSONObject ret = new JSONObject();
        System.out.println(file);
        Environment env = null ;
        try {
            env = new JsonDeserializer().read(file, StandardCharsets.US_ASCII);
        } catch (DeserializationException e) {
            StringWriter sw = new StringWriter();
            PrintWriter pw = new PrintWriter(sw);
            e.printStackTrace(pw);
            ret.put("error_code", E_DESERIALIZATION_ERROR);
            ret.put("error_message", e.getMessage());
            ret.put("details", sw.toString() );
            return ret;
        } catch (FileNotFoundException e) {
            ret.put("error_code", E_INPUT_ERROR);
            ret.put("error_message", e.getMessage());
            return ret;
        }
        String serialized;
        try {
            serialized = new JsonSerializer().write(env);
        } catch (SerializationException e) {
            ret.put("error_code", E_SERIALIZATION_ERROR);
            ret.put("error_message", e.getMessage());
            return ret;
        }
        ret.put("error_code", E_NO_ERROR);
        ret.put("result", serialized);
        return ret;
    }

    private static void walk(File file) {
        System.out.println(file);
        if ( file.isDirectory() ) {
            for ( File child : file.listFiles() )
            {
                walk(child);
            }
        } else {
            JSONObject ret = run_test(file);
            evaluationResults.put(file.getPath(), ret);
        }
    }

    public static void main(String[] args) {
        File TEST_FILES_DIR = new File(args[0]);
        String RESULT_FILE = args[0] + "/results.json";
        walk(TEST_FILES_DIR);
        JSONObject out = new JSONObject();
        out.put("results", evaluationResults);
        try {
            PrintWriter writer = new PrintWriter(RESULT_FILE);
            writer.println(out.toString(4));
            writer.close();
        } catch (java.io.FileNotFoundException e) {
            System.out.println(e.getMessage());
        }
    }
}