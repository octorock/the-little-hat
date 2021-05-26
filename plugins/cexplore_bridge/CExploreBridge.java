//Bridge to The Little Hat and CExplore
//@author octorock
//@category _NEW_
//@keybinding 
//@menupath 
//@toolbar 

// Adapted from https://github.com/radareorg/ghidra-r2web
// Get previous DecompileOptions from https://github.com/NationalSecurityAgency/ghidra/issues/1520

import ghidra.app.script.GhidraScript;
import ghidra.program.model.util.*;
import ghidra.program.model.reloc.*;
import ghidra.program.model.data.*;
import ghidra.program.model.block.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.scalar.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.lang.*;
import ghidra.program.model.pcode.*;
import ghidra.program.model.address.*;
import ghidra.app.decompiler.*;
import com.sun.net.httpserver.*;
import java.io.*;
import java.net.*;
import ghidra.framework.plugintool.util.*;

public class CExploreBridge extends GhidraScript {
	static HttpServer server = null;

	class DecompileHandler implements HttpHandler {
		public void handle(HttpExchange t) throws IOException {
			String name = t.getRequestURI().getPath().toString().substring(11);
			String response;
			int code = 200;
			try {
				response = decompile(name);
			} catch (Exception e) {
				code = 500;
				println(e.toString());
				response = e.toString();
			}
			try {
				byte[] bytes = response.getBytes();
				t.sendResponseHeaders(code, bytes.length);
				OutputStream os = t.getResponseBody();
				os.write(bytes);
				os.close();
			} catch (Exception e) {
				println(e.toString());
			}

		}
	}

	class GoToHandler implements HttpHandler {
		public void handle(HttpExchange t) throws IOException {
			String name = t.getRequestURI().getPath().toString().substring(6);
			String response = "";
			int code = 200;
			try {
				goToFunction(name);
			} catch (Exception e) {
				code = 500;
				response = e.toString();
			}
			try {
				byte[] bytes = response.getBytes();
				t.sendResponseHeaders(code, bytes.length);
				OutputStream os = t.getResponseBody();
				os.write(bytes);
				os.close();
			} catch (Exception e) {
				println(e.toString());
			}

		}
	}

	public void goToFunction(String functionName) {
		Function f = getFunction(functionName);
		if (f == null) {
			throw new RuntimeException("Function " + functionName + " not found.");
		}
		goTo(f);

	}

	public String decompile(String functionName) {
		Function f = getFunction(functionName);
		if (f == null) {
			throw new RuntimeException("Function " + functionName + " not found.");
		}

		// Go to the function so that it can be edited in the next step
		goTo(f);
		DecompInterface di = new DecompInterface();
		// Apply options
		DecompileOptions options = new DecompileOptions();
		var tool = state.getTool();
		if (tool != null) {
			var service = tool.getService(OptionsService.class);
			if (service != null) {
				var opt = service.getOptions("Decompiler");
				options.grabFromToolAndProgram(null, opt, f.getProgram());
			}
		}

		di.setOptions(options);
		println("Simplification style: " + di.getSimplificationStyle());
		println("Debug enables: " + di.debugEnabled());

		println(String.format("Decompiling %s() at 0x%s", f.getName(), f.getEntryPoint().toString()));

		println("Program: " + di.openProgram(getCurrentProgram()));

		// Decompile with a 5-seconds timeout
		DecompileResults dr = di.decompileFunction(f, 5, null);
		println("Decompilation completed: " + dr.decompileCompleted());

		DecompiledFunction df = dr.getDecompiledFunction();
		println(df.getC());
		return df.getC();
	}

	public void run() throws Exception {
		if (server != null) {
			server.stop(0);
		}
		server = HttpServer.create(new InetSocketAddress(10242), 0);
		server.createContext("/decompile", new DecompileHandler());
		server.createContext("/goto", new GoToHandler());
		server.start();

		boolean res = askYesNo("CExplore Bridge is running",
				"Press yes to stop the server.\nPress 'no' to continue in background (EXPERIMENTAL)");
		if (res) {
			server.stop(0);
		}
	}

}
